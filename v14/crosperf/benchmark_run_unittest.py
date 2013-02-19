#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

"""Testing of benchmark_run."""

import unittest

from utils import logger

from autotest_runner import MockAutotestRunner
from benchmark_run import MockBenchmarkRun
from label import MockLabel
from machine_manager import MockMachineManager
from results_cache import MockResultsCache


class BenchmarkRunTest(unittest.TestCase):
  def testDryRun(self):
    my_label = MockLabel("test1", "image1", "/tmp/test_benchmark_run",
                         "x86-alex", "chromeos-alex1", "")
    m = MockMachineManager()
    m.AddMachine("chromeos-alex1", "/tmp/test_benchmark_run")
    b = MockBenchmarkRun("test run",
                         "PageCycler",
                         "Pyautoperf",
                         "",
                         my_label,
                         1,
                         [],
                         0.2,
                         "",
                         m,
                         logger.GetLogger())
    b.cache = MockResultsCache()
    b.autotest_runner = MockAutotestRunner()
    b.start()


if __name__ == "__main__":
  unittest.main()
