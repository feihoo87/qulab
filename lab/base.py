import sys
import tokenize


# yapf: disable
class QuLabError(Exception): pass
class QuLabTypeError(QuLabError): pass
class QuLabRuntimeError(QuLabError): pass
# yapf: enable


class MetaHasSource(type):
    '''MetaHasSource

    Get the source code of Class so we can record it into database.
    '''

    def __new__(cls, name, bases, nmspc):
        return super(MetaApplication, cls).__new__(cls, name, bases, nmspc)

    def __init__(cls, name, bases, nmspc):
        super(MetaApplication, cls).__init__(name, bases, nmspc)
        if cls.__module__ != 'builtins':
            try:
                cls.__source__ = cls._getSourceCode()
            except:
                cls.__source__ = ''

    def _getSourceCode(cls):
        '''getSourceCode
        '''
        module = sys.modules[cls.__module__]
        if module.__name__ == '__main__' and hasattr(module, 'In'):
            code = module.In[-1]
        elif cls.__DBDocument__ is not None:
            try:
                code = cls.__DBDocument__.source
            except:
                raise QuLabTypeError('Document %r has no attribute `source`')
        elif hasattr(module, '__file__'):
            with tokenize.open(module.__file__) as f:
                code = f.read()
        else:
            code = ''
        return code


class HasSource(metaclass=MetaHasSource):
    pass
