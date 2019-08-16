#!/usr/bin/python

# ======================================================================
#   Pollard Rho factorization from Kirby Urner,
#   http://www.mathforum.org/epigone/math-teach/blerlplerdghi
# ======================================================================

#
# Further modified and optimized by Jordan Husney <jordanh@digi.com>
#  - Added acceptance criteria check function.
#  - Changed range() to xrange() generator function.
#

############################################################################
#                                                                          #
# Copyright (c)2008, Digi International (Digi). All Rights Reserved.       #
#                                                                          #
# Permission to use, copy, modify, and distribute this software and its    #
# documentation, without fee and without a signed licensing agreement, is  #
# hereby granted, provided that the software is used on Digi products only #
# and that the software contain this copyright notice,    and the following#
# two paragraphs appear in all copies, modifications, and distributions as #
# well. Contact Product Management, Digi International, Inc., 11001 Bren   #
# Road East, Minnetonka, MN, +1 952-912-3444, for commercial licensing     #
# opportunities for non-Digi products.                                     #
#                                                                          #
# DIGI SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING, BUT NOT LIMITED   #
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A          #
# PARTICULAR PURPOSE. THE SOFTWARE AND ACCOMPANYING DOCUMENTATION, IF ANY, #
# PROVIDED HEREUNDER IS PROVIDED "AS IS" AND WITHOUT WARRANTY OF ANY KIND. #
# DIGI HAS NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT, UPDATES,         #
# ENHANCEMENTS, OR MODIFICATIONS.                                          #
#                                                                          # 
# IN NO EVENT SHALL DIGI BE LIABLE TO ANY PARTY FOR DIRECT, INDIRECT,      #
# SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOST PROFITS,   #
# ARISING OUT OF THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION, EVEN IF   #
# DIGI HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.                #
#                                                                          #
############################################################################


#import common.logging_wrap
from random import randint

#import tracer
from core.tracing import get_tracer
_tracer = get_tracer("rho")

#logger = common.logging_wrap.getLogger('RHO3')

def gen(n,c=1):
    """
    Generate sequence x_i = (x_{i-1}^2 + c) mod n
    Where n is the target composite we want to factor.
    """
    x = 1
    while True:
        x = (x**2 + c) % n
        yield x

def rho(n, maxt=500, maxc=10, test=None):
    """
    Pollard's Rho method for factoring n.
    Returns a list of factors (not necessarily prime) of n.
    Tests each polynomial x^2+c (c in range(1,maxc))
    by following the sequence gen(n,c) for maxt steps.
    If the sequence is cyclic modulo a factor of n
    with a smaller cycle length than its cycle modulo n,
    we can identify a factor of n as the gcd of n
    with the difference of two sequence values separated
    by the smaller cycle length in the sequence.
    """
    if not test:
        test = lambda p, q: True
    if millrab(n):  # don't bother with probable primes
        return [n]
    for c in xrange(1,maxc):
        seqslow = gen(n,c)
        seqfast = gen(n,c)
        for trial in xrange(maxt):
            xb = seqslow.next()        # slow generator goes one step
            seqfast.next()
            xk = seqfast.next()        # while fast generator goes two
            diff = abs(xk-xb)
            if not diff:
                continue
            d = gcd(diff,n)        # have a factor?
            if n>d>1:
                f = n//d
                if test(d,f):
                    return [d,f]
                continue
    return [n]      # failure to factor

def gcd(a,b):
    """
    Euclid's algorithm for integer greatest common divisors.
    """
    while b:
        a,b = b,a%b
    return a

def millrab(n, max=30):
    """
    Miller-Rabin primality test as per the following source:
    http://www.wikipedia.org/wiki/Miller-Rabin_primality_test
    Returns probability p is prime: either p = 0 or ~1,
    """
    if not n%2: return 0
    k = 0
    z = n - 1

    # compute m,k such that (2**k)*m = n-1
    while not z % 2:
      k += 1
      z //= 2
    m = z

    # try tests with max random integers between 2,n-1
    ok = 1
    trials = 0
    p = 1
    while trials < max and ok:
        a = randint(2,n-1)
        trials += 1
        test = pow(a,m,n)
        if (not test == 1) and not (test == n-1):
            # if 1st test fails, fall through
            ok = 0
            for r in range(1,k):
                test = pow(a, (2**r)*m, n)
                if test == (n-1):
                    ok = 1 # 2nd test ok
                    break
        else: ok = 1  # 1st test ok
        if ok==1:  p *= 0.25

    if ok:  return 1 - p
    else:   return 0

if __name__ == '__main__':

    import sys
    argv = sys.argv[1:]
    criteria = lambda p, q: (p >= 0x20 and p <= 0xAF0) and q <= 0xffff
    _tracer.info(rho(int(argv[0]), test=criteria))
