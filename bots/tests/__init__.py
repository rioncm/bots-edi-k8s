# -*- coding: utf-8 -*-

from bots import botsinit, botsglobal

import unittest


botsinit.generalinit('config')
botsglobal.logger = botsinit.initenginelogging('unitest')
#~ botslib.initbotscharsets()


def run_unitests():
    """Return unittest test suite to run
    """
    loader = unittest.TestLoader()
    test_suite = loader.discover('.', pattern='uniturl.py')
    # test_suite = loader.discover('.', pattern='unit*.py')
    return test_suite



class BotsTestCase(unittest.TestCase):
    pass
