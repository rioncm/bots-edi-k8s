# -*- coding: utf-8 -*-
"""
Bots django app config
"""

from django.apps import AppConfig

from . import __about__ as about


class Config(AppConfig):
    """Django app config"""
    # pylint: disable=too-few-public-methods
    name = __package__
    verbose_name = about.__summary__
