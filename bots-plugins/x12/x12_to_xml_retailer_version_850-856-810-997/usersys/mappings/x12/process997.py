# bots mapping-script
from bots.botsconfig import *
from bots import botslib


def main(inn, out):
    # indicate: no output form translation.
    out.ta_info['statust'] = DONE
    reference = inn.get({'BOTSID': 'ST'}, {'BOTSID': 'AK1', 'AK102': None})
    botslib.changeq('''
        UPDATE ta
        SET   confirmed=%(confirmed)s, confirmidta=%(confirmidta)s
        WHERE reference=%(reference)s
        AND   status=%(status)s
        AND   confirmasked=%(confirmasked)s
        AND   confirmtype=%(confirmtype)s
        AND   frompartner=%(frompartner)s
        AND   topartner=%(topartner)s
        ''',
        {
            'status': MERGED,
            'reference': reference,
            'confirmed': True,
            'confirmtype': 'ask-x12-997',
            'confirmidta': inn.ta_info['idta_fromfile'],
            'confirmasked': True,
            'frompartner': inn.ta_info['topartner'],
            'topartner': inn.ta_info['frompartner'],
        }
    )
    # NOTE: no error is given when 997 can not be matched.
    # NOTE: botslib.changeq works as of bots3.0.0; before this was: botslib.change
