#!/usr/bin/env python
import cProfile
import pstats


if __name__ == '__main__':

    cProfile.run('from bots import engine; engine.start()','profile.tmp')

    pst = pstats.Stats('profile.tmp')
    #~ pst.sort_stats('cumulative').print_stats(25)
    pst.sort_stats('time').print_stats(50)
    #~ pst.print_callees('deepcopy').print_stats(1)
    pst.print_callees('mydeepcopy')
    #~ pst.sort_stats('time').print_stats('grammar.py',50)
