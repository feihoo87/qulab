# -*- coding: utf-8 -*-
import numpy as np
import time

from lab.device import BaseDriver
from lab.device import QReal, QOption, QInteger, QString, QVector

class Driver(BaseDriver):
    error_command = ''
    surport_models = ['DG645']

    quants = [
        QReal('Trigger Rate', unit='Hz', set_cmd='TRAT %(value).6E', get_cmd='TRAT?'),

        QReal('T0 Amplitude', unit='V', set_cmd='LAMP 0,%(value).2f', get_cmd='LAMP?0'),
        QReal('T0 Offset', unit='V', set_cmd='LOFF 0,%(value).2f', get_cmd='LOFF?0'),
        QReal('T0 Length', unit='s', set_cmd='DLAY 1,0,%(value).6E', get_cmd='DELY?1'),

        QReal('AB Amplitude', unit='V', set_cmd='LAMP 1,%(value).2f', get_cmd='LAMP?1'),
        QReal('AB Offset', unit='V', set_cmd='LOFF 1,%(value).2f', get_cmd='LOFF?1'),
        QReal('AB Delay', unit='s', set_cmd='DLAY 2,0,%(value).6E', get_cmd='DELY?2'),
        QReal('AB Length', unit='s', set_cmd='DLAY 3,2,%(value).6E', get_cmd='DELY?3'),

        QReal('CD Amplitude', unit='V', set_cmd='LAMP 2,%(value).2f', get_cmd='LAMP?2'),
        QReal('CD Offset', unit='V', set_cmd='LOFF 2,%(value).2f', get_cmd='LOFF?2'),
        QReal('CD Delay', unit='s', set_cmd='DLAY 4,0,%(value).6E', get_cmd='DELY?4'),
        QReal('CD Length', unit='s', set_cmd='DLAY 5,4,%(value).6E', get_cmd='DELY?5'),

        QReal('EF Amplitude', unit='V', set_cmd='LAMP 3,%(value).2f', get_cmd='LAMP?3'),
        QReal('EF Offset', unit='V', set_cmd='LOFF 3,%(value).2f', get_cmd='LOFF?3'),
        QReal('EF Delay', unit='s', set_cmd='DLAY 6,0,%(value).6E', get_cmd='DELY?6'),
        QReal('EF Length', unit='s', set_cmd='DLAY 7,6,%(value).6E', get_cmd='DELY?7'),

        QReal('GH Amplitude', unit='V', set_cmd='LAMP 4,%(value).2f', get_cmd='LAMP?4'),
        QReal('GH Offset', unit='V', set_cmd='LOFF 4,%(value).2f', get_cmd='LOFF?4'),
        QReal('GH Delay', unit='s', set_cmd='DLAY 8,0,%(value).6E', get_cmd='DELY?8'),
        QReal('GH Length', unit='s', set_cmd='DLAY 9,8,%(value).6E', get_cmd='DELY?9')

    ]
