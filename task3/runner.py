# MIT License
#
# Copyright (c) 2016 Olivier Bachem
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""Map Reduce Framework for Python (Task3, DM2016)

https://project.las.ethz.ch/task3

1. The framework first loads the python source code specified in `sourcefile`.
  The source should contain a `mapper` and a `reducer` function.
  The `mapper(key, value)` function takes as input a (key, value) tuple where
  key is None and value is a string. It should yield (key, value) pairs.
  The `reducer(key, value)` function takes as input a key and a list of values.
  It should yield (key, value) pairs.

The source of a word count program looks as follows:

>>> def mapper(key, value):
>>>     for i in value.split():
>>>         yield i, 1
>>>
>>> def reducer(key, values):
>>>     yield key, sum(values)

2. Implementation details:
  - Keys produced by the mapper *must* only be strings, ints or floats.
  - The (key, value) pairs produced by the mapper must be pickable by cPickle
    (https://docs.python.org/2/library/pickle.html).
  - The (key, value) pairs produced by the reducer must be convertable to JSON
    (https://docs.python.org/2/library/json.html?).

3. The training files are then used to run the example.

4. For debugging purposes, logging to STDERR can be enabled using the `--log` or `-l` flag.

(c) 2016 Olivier Bachem
"""
from collections import defaultdict
from itertools import chain, islice, izip
import argparse
import glob
import imp
import multiprocessing
import numpy as np
import os
import random
import sys
import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


def chunks(iterable, size=10):
    iterator = iter(iterable)
    for first in iterator:
        yield list(chain([first], islice(iterator, size - 1)))


def isolated_batch_call(f, arguments):
    """Calls the function f in a separate process and returns list of results"""

    def lf(q):
        result_generator = f(*arguments)
        result = list(result_generator)
        q.put(result)
        
    q = multiprocessing.Queue()
    p = multiprocessing.Process(target=lf, args=(q, ))
    p.start()
    ret = q.get()
    p.join()
    return ret


def mapreduce(input, mapper, reducer, batch_size=50, log=False):
    """Python function that runs a worst-case map reduce framework on the provided data

    Args:
      input -- list or generator of (key, value) tuple
      mapper -- function that takes (key, value) pair as input and returns iterable key-value pairs
      reducer -- function that takes key + list of values and outputs (key, value) pair
      log -- whether log messages should be generated (default: False)

    Returns list of (key, value pairs)
    """
    # Set initial random seed
    random.seed(0)
    # Run mappers
    if log: logger.info("Starting mapping phase!")
    d = defaultdict(list)
    for pairs_generator in chunks(input, batch_size):
        pairs = np.array(pairs_generator)
        if log: logger.debug("  Running mapper for '%s' key with value '%s'...", k, v)
        for k2, v2 in isolated_batch_call(mapper, (None, pairs)):
        # for k2, v2 in mapper(None, pairs):
            if log: logger.debug("    Mapper produced (%s, %s) pair...", k2, v2)
            if not isinstance(k2, (basestring, int, float)):
                raise Exception("Keys must be strings, ints or floats (provided '%s')!"% k2)
            d[k2].append(v2)
    if log: logger.info("Finished mapping phase!")
    # Random permutations of both keys and values.
    keys = d.keys()
    random.shuffle(keys)
    for k in keys:
        random.shuffle(d[k])
    # Run reducers
    if log: logger.info("Starting reducing phase!")
    res = []
    if len(keys) > 1:
        raise Exception("Only one distinct key expected from mappers.")
    k = keys[0]
    v = np.vstack(d[k])
    r = isolated_batch_call(reducer, (k, v))
    if log: logger.debug("    Reducer produced %s", r)
    logger.info("Finished reducing phase!")
    return r


def yield_pattern(path):
    """Yield lines from each file in specified folder"""
    for i in glob.iglob(path):
        if os.path.isfile(i):
            with open(i, "r") as fin:
                for line in fin:
                    yield None, line


def import_from_file(f):
    """Import code from the specified file"""
    mod = imp.new_module("mod")
    exec f in mod.__dict__
    return mod


def evaluate(points, centers):
    score = 0.0
    for chunk in chunks(points, 20):
        batch = np.array(chunk)
        score += np.square(batch[:,np.newaxis,:] - centers).sum(axis=2).min(axis=1).sum()
    return score / points.shape[0]
    
    
def run(sourcestring, training_file, test_file, batch, log):
    mod = import_from_file(sourcestring)
    training_data = np.load(training_file)
    output = mapreduce(training_data, mod.mapper, mod.reducer, batch, log)
    centers = np.vstack(output)
    test_data = np.load(test_file)
    return evaluate(test_data, centers)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        'train_file', help='File with the training instances')
    parser.add_argument(
        'test_file', help='File with the test instances')
    parser.add_argument(
        'source_file', help='.py file with mapper and reducer function')
    parser.add_argument(
        '--log', '-l', help='Enable logging for debugging', action='store_true')
    args = parser.parse_args()
    BATCH = 10000
    
    with open(args.source_file, "r") as fin:
        source = fin.read()

    print run(source, args.train_file, args.test_file, BATCH, args.log)

if __name__ == "__main__":
    main()
