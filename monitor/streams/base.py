import abc
from collections import deque

class abstractclassmethod(classmethod):
    """ Decorator for a abstract class method. """
    __isabstractmethod__ = True

    def __init__(self, callable):
        callable.__isabstractmethod__ = True
        super(abstractclassmethod, self).__init__(callable)

class BaseStream(object):
    """ Base class to provide a stream of data to NuPIC. """
    __metaclass__ = abc.ABCMeta

    @abc.abstractproperty
    def  value_label(self):
        """ Label of the value being streamed """
        pass

    @abc.abstractproperty
    def  value_unit(self):
        """ Unit of the value being streamed """
        pass

    def __init__(self, config):
        # Get stream_id from config
        self.id = config['id']

        # Get stream name from config (default to self.id)
        self.name = config['name']

        # Time to keep watch for new values
        self.servertime = None
        
        # Deque to keep history of input values for smoothing
        moving_average_window = config['moving_average_window'] 
        self.history = deque([0.0] * moving_average_window, maxlen=moving_average_window)

    @abc.abstractmethod
    def historic_data(self):
        """ Return a list of data to be used at training. 
            Should return a structure like this: 
                [{'value': v1, 'time': t1}, {'value': v2, 'time': t2}] 
        """
        pass

    @abc.abstractmethod
    def new_data(self):
        """ Return a list of new data since last update.
            Should return a structure like this: 
                [{'value': v1, 'time': t1}, {'value': v2, 'time': t2}] 
        """
        pass

    @abstractclassmethod
    def available_streams(cls, credentials):
        """ Return a list with available streams for the class implementing this. Should return a list : 
                [{'id': i1, 'name': n1}, {'id': i2, 'name': n2}] 
        """
        pass

    def _moving_average(self):
        """ Used to smooth input data. """

        return sum(self.history)/len(self.history) if len(self.history) > 0 else 0 