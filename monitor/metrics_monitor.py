#!/usr/bin/env python
# ----------------------------------------------------------------------
# Numenta Platform for Intelligent Computing (NuPIC)
# Copyright (C) 2013, Numenta, Inc.  Unless you have purchased from
# Numenta, Inc. a separate commercial license for this software code, the
# following terms and conditions apply:
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see http://www.gnu.org/licenses.
#
# http://numenta.org/licenses/
# ----------------------------------------------------------------------

"""A simple client to create a CLA model for Monitor."""

from datetime import datetime
from collections import deque
import sys
import os
import thread
import logging
import logging.handlers
from time import strftime, gmtime, sleep

from nupic.frameworks.opf.modelfactory import ModelFactory
from nupic.data.inference_shifter import InferenceShifter
import model_params_monitor # file containing CLA parameters

import redis
from utils import pingdom # Pingdom API wrapper
from utils import anomaly_likelihood

_TIMEOUT = 30000 # Default response time when status is not 'up' (ms)
_SECONDS_PER_REQUEST = 60 # Sleep time between requests (in seconds)

# Connect to redis server
_REDIS_SERVER = redis.Redis("localhost")

# Top logger (for redis). Will use only when stand-alone.
logger = logging.getLogger(__name__)

# Test the redis server
try:
    response = _REDIS_SERVER.client_list()
except redis.ConnectionError:
    logger.error("Redis server is down.")
    sys.exit(0)

def moving_average(data):
    """ Used to eventually smooth input data. Not used now. """
    return sum(data)/len(data) if len(data) > 0 else 0 

def create_model():
    """ Create the CLA model """
    return ModelFactory.create(model_params_monitor.MODEL_PARAMS)

def run(check_id, check_name, check_url):
    """ Main loop, responsible for online training """

    # Setup logging
    logger = logging.getLogger(__name__)
    handler = logging.handlers.RotatingFileHandler(os.environ['LOG_DIR']+"/monitor_%s.log" % check_name,
                                                    maxBytes=1024*1024,
                                                    backupCount=4,
                                                    )

    formatter = logging.Formatter('[%(levelname)s/%(processName)s][%(asctime)s] %(name)s %(message)s')
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    # The shifter is used to bring the predictions to the actual time frame
    shifter = InferenceShifter()
    
    # The anomaly likelihood object
    anomalyLikelihood = anomaly_likelihood.AnomalyLikelihood()

    model = create_model() # Create the CLA model

    model.enableInference({'predictedField': 'responsetime'})

    # Moving average window for response time smoothing (higher means smoother)
    MAVG_WINDOW = 30

    # Deque to keep history of response time input for smoothing
    history = deque([0.0] * MAVG_WINDOW, maxlen=MAVG_WINDOW)


    logger.info("[%s] Let's start learning online..." % check_name)

    import time

    

    servertime = None 

    while True:        
        modelInput = {'time': int(time.time()), 'responsetime': 420, 'status': 'OK'}            
        # If any result contains new responses (ahead of [servetime]) process it. 
        # We check the last 5 results, so that we don't many lose data points.
        if servertime < int(modelInput['time']):
            # Update servertime
            servertime = int(modelInput['time'])
            modelInput['time'] = datetime.utcfromtimestamp(servertime)

            # If not have response time is because it's not up, so set it to a large number
            if 'responsetime' not in modelInput:
                modelInput['responsetime'] = _TIMEOUT

            history.appendleft(int(modelInput['responsetime']))
            modelInput['responsetime'] = moving_average(history)

            # Pass the input to the model
            result = model.run(modelInput)
            # Shift results
            result = shifter.shift(result)
            # Save multi step predictions 
            inference = result.inferences['multiStepPredictions']
            # Take the anomaly_score
            anomaly_score = result.inferences['anomalyScore']
            # Compute the Anomaly Likelihood
            likelihood = anomalyLikelihood.anomalyProbability(
                modelInput['responsetime'], anomaly_score, modelInput['time'])
            
            logger.info("[%s][online] Processing: %s" % (check_name, strftime("%Y-%m-%d %H:%M:%S", gmtime(servertime))))

            if inference[1]:
                try:
                    # Save in redis with key = 'results:check_id' and value = 'time, status, actual, prediction, anomaly'
                    _REDIS_SERVER.rpush('results:%d' % check_id, '%s,%s,%d,%d,%.5f,%.5f' % (servertime,modelInput['status'],result.rawInput['responsetime'],result.inferences['multiStepBestPredictions'][1],anomaly_score, likelihood))
                except Exception, e:
                    logger.warn("[%s] Could not write results to redis." % check_name, exc_info=True)
                    continue
            else:
                    logger.warn("[%s] Don't have inference[1]: %s." % (check_name, inference))

            sleep(1)        
            

