import abc
import asyncio
import functools
import importlib
import sys
import tokenize
from collections import Awaitable, Iterable, OrderedDict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from threading import Thread

import numpy as np

from ._bootstrap import get_current_user, open_resource, save_inputCells
from ._plot import draw
from .base import HasSource
from .db import _schema
from .ui import ApplicationUI, display_source_code


class Application(HasSource, abc.ABC):
    __source__ = ''
    __DBDocument__ = None

    def __init__(self, parent=None):
        self.parent = parent
        self.rc = RcMap()
        self.data = DataCollector(self)
        self.settings = {}
        self.params = {}
        self.tags = []
        self.sweep = SweepSet(self)
        self.status = None
        self.ui = None
        self.reset_status()
        self.level = 1
        self.level_limit = 3

        if parent is not None:
            self.rc.parent = parent.rc
            self.settings.update(parent.settings)
            self.params.update(parent.params)
            self.params.update(parent.status['current_params'])
            self.tags.extend(parent.tags)
            self.level = parent.level + 1
            self.level_limit = parent.level_limit
            #parent.status['sub_process_num'] += 1

    def __del__(self):
        if self.parent is not None:
            #self.parent.status['sub_process_num'] -= 1
            pass

    def reset(self):
        self.reset_status()
        self.data.clear()
        # self.ui.reset()

    def title(self):
        version = '%s.%d' % (self.__DBDocument__.version_tag,
                             self.__DBDocument__.version)
        return 'Record by %s (%s)' % (self.__class__.__name__, version)

    def reset_status(self):
        self.status = dict(
            current_record=None,
            current_params={},
            last_step_process=0,
            sub_process_num=1,
            process_changed_by_children=False,
            process=0.0,
            done=False,
        )

    def getTotalProcess(self):
        if self.parent is None:
            return 100.0
        else:
            return self.parent.status['last_step_process'] / max(
                self.parent.status['sub_process_num'], 1)

    def processToChange(self, delta):
        self.status['last_step_process'] = delta

    def increaseProcess(self, value=0, by_children=False):
        if not self.status['process_changed_by_children']:
            value = self.status['last_step_process']
            self.status['process'] += value
        elif by_children:
            self.status['process'] += value
        if self.parent is not None:
            self.parent.status['process_changed_by_children'] = True
            self.parent.increaseProcess(
                value * self.getTotalProcess() / 100, by_children=True)
        if self.ui is not None:
            self.ui.setProcess(self.status['process'])

    def with_rc(self, rc={}):
        self.rc.update(rc)
        return self

    def with_tags(self, *tags):
        for tag in tags:
            if tag not in self.tags:
                self.tags.append(tag)
        return self

    def with_params(self, **kwargs):
        params = dict([(name, [v[0], v[1]])
                       if isinstance(v, (list, tuple)) else (name, [v, ''])
                       for name, v in kwargs.items()])
        self.params.update(params)
        return self

    def with_settings(self, settings={}):
        self.settings.update(settings)
        return self

    def setDone(self):
        self.status['done'] = True
        #value = 100 - self.ui.get_process()
        # self.increase_process(value)

    def run(self):
        self.ui = ApplicationUI(self)
        self.ui.display()
        with ThreadPoolExecutor() as executor:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.set_default_executor(executor)
            tasks = [asyncio.ensure_future(self.done())]
            loop.run_until_complete(asyncio.wait(tasks))
            loop.close()
        save_inputCells()

    async def done(self):
        self.reset()
        async for data in self.work():
            self.data.collect(data)
            result = self.data.result()
            if self.level <= self.level_limit:
                self.data.save()
            draw(self.__class__.plot, result, self)
        self.setDone()
        return self.data.result()

    async def work(self):
        '''单个返回值不要用 tuple，否则会被解包，下面这些都允许
        yield 0
        yield 0, 1, 2
        yield np.array([1,2,3])
        yield [1,2,3]
        yield 1, (1,2)
        yield 0.5, np.array([1,2,3])
        '''

    def pre_save(self, *args):
        return args

    @staticmethod
    def plot(fig, data):
        pass

    @classmethod
    def save(cls, version=None, moduleName=None):
        _schema.saveApplication(cls.__name__, cls.__source__,
                                get_current_user(), cls.__doc__, moduleName,
                                version)

    @classmethod
    def show(cls):
        display_source_code(cls.__source__)


class DataCollector:
    '''Collect data when app runs'''
    def __init__(self, app):
        self.app = app
        self.clear()

    def clear(self):
        self.__data = None
        self.__rows = 0
        self.__cols = 0
        self.__record = None

    @property
    def cols(self):
        return self.__cols

    @property
    def rows(self):
        return self.__rows

    def collect(self, data):
        '''对于存在循环的实验，将每一轮生成的数据收集起来'''
        if not isinstance(data, tuple):
            data = (data, )
        if self.__data is None:
            self.__data = [[v] for v in data]
            self.__cols = len(data)
            self.__rows = 1
        else:
            for i, v in enumerate(data):
                self.__data[i].append(v)
            self.__rows += 1

    def result(self):
        '''将收集到的数据按 work 生成时的顺序返回'''
        if self.__rows == 1:
            data = tuple([v[0] for v in self.__data)
        else:
            data = tuple([np.array(v) for v in self.__data)
        if self.__rows == 1:
            return self.app.pre_save(data[0])
        else:
            return self.app.pre_save(*data)

    def save(self):
        if self.__record is None:
            self.__record = self.newRecord()
        self.__record.data = data
        self.__record.save(signal_kwargs=dict(finished=True))

    def newRecord(self):
        rc = dict([(name, str(v)) for name, v in self.app.rc.items()])
        record = _schema.Record(
            title=self.app.title(),
            user=get_current_user(),
            tags=self.app.tags,
            params=self.app.params,
            rc=rc,
            hidden=False if self.app.parent is None else True,
            app=self.app.__DBDocument__,
        )
        #self.status['current_record'] = record
        if self.app.parent is not None:
            self.app.parent.data.addSubRecord(record)
        return record

    def addSubRecord(self, record):
        if self.__record is not None:
            if record.id is None:
                record.save(signal_kwargs=dict(finished=True))
            self.__record.children.append(record)
            self.__record.save(
                signal_kwargs=dict(finished=True))


class Sweep:
    """Sweep

    Sweep channal config.
    """

    def __init__(self,
                 name,
                 generator,
                 unit='',
                 setter=None,
                 start=None,
                 total=None):
        self.name = name
        self.generator = generator
        self.unit = unit
        self.setter = setter
        self.start = start
        self.total = total
        self._generator = self.generator

    def __call__(self, *args, **kwds):
        self._generator = self._generator(*args, **kwds)
        return self

    def __len__(self):
        try:
            return len(self._generator)
        except TypeError:
            return self.total

    def __aiter__(self):
        return SweepIter(self)


class SweepIter:
    def __init__(self, sweep):
        self.iter = sweep._generator.__iter__() if isinstance(
            sweep._generator, Iterable) else sweep._generator
        self.app = sweep.app
        self.setter = sweep.setter
        self.name = sweep.name
        self.unit = sweep.unit
        self.lenght = len(sweep)

    def fetch_data(self):
        try:
            data = next(self.iter)
        except StopIteration:
            raise StopAsyncIteration
        return data

    async def set_data(self, data):
        if self.setter is not None:
            ret = self.setter(data)
        elif self.app is not None and hasattr(self.app, 'set_%s' % self.name):
            ret = getattr(self.app, 'set_%s' % self.name).__call__(data)
        else:
            print(self.name, 'not set', self.app.__class__.__name__)
            return
        if isinstance(ret, Awaitable):
            await ret

    async def __anext__(self):
        if self.app is not None:
            self.app.increaseProcess()
        data = self.fetch_data()
        await self.set_data(data)
        if self.app is not None:
            self.app.status['current_params'][self.name] = [
                float(data), self.unit
            ]
            if self.lenght is not None:
                self.app.processToChange(100.0 / self.lenght)
        return data


class SweepSet:
    def __init__(self, app):
        self.app = app
        self._sweep = {}
        if app.parent is not None:
            self._sweep.update(app.parent.sweep._sweep)

    def __getitem__(self, name):
        return self._sweep[name]

    def __call__(self, sweeps=[]):
        for args in sweeps:
            if isinstance(args, tuple):
                sweep = Sweep(*args)
            elif isinstance(args, dict):
                sweep = Sweep(**args)
            elif isinstance(args, Sweep):
                sweep = args
            else:
                raise TypeError('Unsupport type %r for sweep.' % type(args))
            self._sweep[sweep.name] = sweep
        return self.app


class RcMap:
    def __init__(self, rc={}, parent=None):
        self.rc = {}
        self.parent = parent
        self.rc.update(rc)

    def update(self, rc={}):
        self.rc.update(rc)

    def items(self):
        return [(name, self.__getitem__(name)) for name in self.keys()]

    def keys(self):
        keys = set(self.rc.keys())
        if self.parent is not None:
            keys = keys.union(self.parent.keys())
        return list(keys)

    def get(self, name, default=None):
        if name in self.keys():
            return self.get_resource(name)
        elif default is None:
            raise KeyError('key %r not found in RcMap.' % name)
        else:
            return default

    def get_resource(self, name):
        name = self.rc.get(name, name)
        if not isinstance(name, str):
            return name
        elif self.parent is not None:
            return self.parent.get_resource(name)
        else:
            return open_resource(name)

    def __getitem__(self, name):
        return self.get(name)


def getAppClass(name='', version=None, id=None, **kwds):
    appdata = _schema.getApplication(name, version, id, **kwds)
    if appdata is None:
        return None
    mod = importlib.import_module(appdata.module.fullname)
    app_cls = getattr(mod, name)
    app_cls.__DBDocument__ = appdata
    app_cls.__source__ = appdata.source
    return app_cls


def make_app(name, version=None, parent=None):
    app_cls = getAppClass(name, version)
    return app_cls(parent=parent)
