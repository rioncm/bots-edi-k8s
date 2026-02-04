# -*- coding: utf-8 -*-
"""
Bots django filtertags
"""
# pylint: disable=missing-function-docstring, broad-exception-caught

import os
from typing import List

from django import template
from django.utils.translation import gettext as _

from bots import models


register = template.Library()


@register.filter
def shortpath(path):
    if path:
        if isinstance(path, int):
            return str(path)
        # url path
        if '://' in path:
            return path
        return os.path.basename(path) or f"({_('file')})"  # In some cases, there is no good filename.....
    return ''


def adminlinkfilter(query, key, field=None):
    path = '?e=1'
    if query:
        count = query.count()
        if count == 1:
            return f"{query.first().pk}/change/?"
        if count >> 1:
            if field:
                return f"?{field}={key}&"
            return f"?q={key}&"
    return path


@register.filter
def adminlinker(key, ct):
    if ct == 'routes':
        try:
            query = models.routes.objects.filter(idroute=key)
            return adminlinkfilter(query, key, field='idroute')
        except Exception:
            pass
    return '?e=1'


@register.filter
def get_translate(frommessagetype, tscript):
    try:
        translates = models.translate.objects.filter(
            frommessagetype=frommessagetype, tscript=tscript)
        if translates.count() == 1:
            return translates.first()
        if translates.count() > 1:
            return translates.filter(active=True).first()
    except Exception:
        pass
    return None


@register.filter
def get_channel(idchannel):
    return models.channel.objects.filter(idchannel=idchannel).first()


@register.filter
def get_channel_type(idchannel, channels_types=None):
    if channels_types:
        return channels_types.get(idchannel)
    channel = get_channel(idchannel)
    return channel.type if channel else None


@register.filter
def get_choice_display(value, choices):
    """Return text displayed in choices list for value"""
    for choice in choices:
        if choice[0] == value:
            return choice[1]
    return value


@register.filter
def inchoices(value, choices: List[tuple]) -> bool:
    """Return True if value is in choices tuple list"""
    return value in [v[0] for v in choices]
