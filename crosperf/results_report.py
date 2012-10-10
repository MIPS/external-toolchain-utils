#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import math
from column_chart import ColumnChart
from results_sorter import ResultSorter
from results_organizer import ResultOrganizer
from utils.tabulator import *

class ResultsReport(object):
  MAX_COLOR_CODE = 255

  def __init__(self, experiment):
    self.experiment = experiment
    self.benchmark_runs = experiment.benchmark_runs
    self.labels = experiment.labels
    self.benchmarks = experiment.benchmarks
    self.baseline = self.labels[0]

  def _SortByLabel(self, runs):
    labels = {}
    for benchmark_run in runs:
      if benchmark_run.label_name not in labels:
        labels[benchmark_run.label_name] = []
      labels[benchmark_run.label_name].append(benchmark_run)
    return labels

  def GetFullTables(self):
    columns = [Column(NonEmptyCountResult(),
                      Format(),
                      "Completed"),
               Column(RawResult(),
                      Format()),
               Column(MinResult(),
                      Format()),
               Column(MaxResult(),
                      Format()),
               Column(AmeanResult(),
                      Format()),
               Column(StdResult(),
                      Format())
              ]
    return self._GetTables(self.labels, self.benchmark_runs, columns)

  def GetSummaryTables(self):
    columns = [Column(AmeanResult(),
                      Format()),
               Column(StdResult(),
                      Format(), "StdDev"),
               Column(CoeffVarResult(),
                      CoeffVarFormat(), "Mean/StdDev"),
               Column(GmeanRatioResult(),
                      RatioFormat(), "GmeanSpeedup"),
               Column(GmeanRatioResult(),
                      ColorBoxFormat(), " "),
               Column(StatsSignificant(),
                      Format(), "p-value")
              ]
    return self._GetTables(self.labels, self.benchmark_runs, columns)

  def _ParseColumn(self, columns, iteration):
    new_column = []
    for column in columns:
      if column.result.__class__.__name__ != "RawResult":
      #TODO(asharif): tabulator should support full table natively.
        new_column.append(column)
      else:
        for i in range(iteration):
          cc = Column(LiteralResult(i), Format(), str(i+1))
          new_column.append(cc)
    return new_column

  def _AreAllRunsEmpty(self, runs):
    for label in runs:
      for dictionary in label:
        if dictionary:
          return False
    return True

  def _GetTables(self, labels, benchmark_runs, columns):
    tables = []
    ro = ResultOrganizer(benchmark_runs, labels)
    result = ro.result
    label_name = ro.labels
    for item in result:
      runs = result[item]
      for benchmark in self.benchmarks:
        if benchmark.name == item:
          break
      benchmark_info = ("Benchmark:  {0};  Iterations: {1}"
                         .format(benchmark.name, benchmark.iterations))
      cell = Cell()
      cell.string_value = benchmark_info
      ben_table = [[cell]]

      if  self._AreAllRunsEmpty(runs):
        cell = Cell()
        cell.string_value = ("This benchmark contains no result."
                             " Is the benchmark name valid?")
        cell_table = [[cell]]
      else:
        tg = TableGenerator(runs, label_name)
        table = tg.GetTable()
        parsed_columns = self._ParseColumn(columns, benchmark.iterations)
        tf = TableFormatter(table, parsed_columns)
        cell_table = tf.GetCellTable()
      tables.append(ben_table)
      tables.append(cell_table)
    return tables

  def PrintTables(self, tables, out_to):
    output = ""
    for table in tables:
      if out_to == "HTML":
        tp = TablePrinter(table, TablePrinter.HTML)
      elif out_to == "PLAIN":
        tp = TablePrinter(table, TablePrinter.PLAIN)
      elif out_to == "CONSOLE":
        tp = TablePrinter(table, TablePrinter.CONSOLE)
      elif out_to == "TSV":
        tp = TablePrinter(table, TablePrinter.TSV)
      elif out_to == "EMAIL":
        tp = TablePrinter(table, TablePrinter.EMAIL)
      else:
        pass
      output += tp.Print()
    return output
class TextResultsReport(ResultsReport):
  TEXT = """
===========================================
Results report for: '%s'
===========================================

-------------------------------------------
Summary
-------------------------------------------
%s

-------------------------------------------
Experiment File
-------------------------------------------
%s
===========================================
"""

  def __init__(self, experiment, email=False):
    super(TextResultsReport, self).__init__(experiment)
    self.email = email

  def GetReport(self):
    summary_table = self.GetSummaryTables()
    full_table = self.GetFullTables()
    if not self.email:
      return self.TEXT % (self.experiment.name,
                          self.PrintTables(summary_table, "CONSOLE"),
                          self.experiment.experiment_file)

    return self.TEXT % (self.experiment.name,
                        self.PrintTables(summary_table, "EMAIL"),
                        self.experiment.experiment_file)


class HTMLResultsReport(ResultsReport):

  HTML = """
<html>
  <head>
    <style type="text/css">

body {
  font-family: "Lucida Sans Unicode", "Lucida Grande", Sans-Serif;
  font-size: 12px;
}

pre {
  margin: 10px;
  color: #039;
  font-size: 14px;
}

.chart {
  display: inline;
}

.hidden {
  visibility: hidden;
}

.results-section {
  border: 1px solid #b9c9fe;
  margin: 10px;
}

.results-section-title {
  background-color: #b9c9fe;
  color: #039;
  padding: 7px;
  font-size: 14px;
  width: 200px;
}

.results-section-content {
  margin: 10px;
  padding: 10px;
  overflow:auto;
}

#box-table-a {
  font-size: 12px;
  width: 480px;
  text-align: left;
  border-collapse: collapse;
}

#box-table-a th {
  padding: 6px;
  background: #b9c9fe;
  border-right: 1px solid #fff;
  border-bottom: 1px solid #fff;
  color: #039;
  text-align: center;
}

#box-table-a td {
  padding: 4px;
  background: #e8edff;
  border-bottom: 1px solid #fff;
  border-right: 1px solid #fff;
  color: #669;
  border-top: 1px solid transparent;
}

#box-table-a tr:hover td {
  background: #d0dafd;
  color: #339;
}

    </style>
    <script type='text/javascript' src='https://www.google.com/jsapi'></script>
    <script type='text/javascript'>
      google.load('visualization', '1', {packages:['corechart']});
      google.setOnLoadCallback(init);
      function init() {
        switchTab('summary', 'html');
        switchTab('full', 'html');
        drawTable();
      }
      function drawTable() {
        %s
      }
      function switchTab(table, tab) {
        document.getElementById(table + '-html').style.display = 'none';
        document.getElementById(table + '-text').style.display = 'none';
        document.getElementById(table + '-tsv').style.display = 'none';
        document.getElementById(table + '-' + tab).style.display = 'block';
      }
    </script>
  </head>

  <body>
    <div class='results-section'>
      <div class='results-section-title'>Summary Table</div>
      <div class='results-section-content'>
        <div id='summary-html'>%s</div>
        <div id='summary-text'><pre>%s</pre></div>
        <div id='summary-tsv'><pre>%s</pre></div>
      </div>
      %s
    </div>
    <div class='results-section'>
      <div class='results-section-title'>Charts</div>
      <div class='results-section-content'>%s</div>
    </div>
    <div class='results-section'>
      <div class='results-section-title'>Full Table</div>
      <div class='results-section-content'>
        <div id='full-html'>%s</div>
        <div id='full-text'><pre>%s</pre></div>
        <div id='full-tsv'><pre>%s</pre></div>
      </div>
      %s
    </div>
    <div class='results-section'>
      <div class='results-section-title'>Experiment File</div>
      <div class='results-section-content'>
        <pre>%s</pre>
    </div>
    </div>
  </body>
</html>
"""

  def __init__(self, experiment):
    super(HTMLResultsReport, self).__init__(experiment)

  def _GetTabMenuHTML(self, table):
    return """
<div class='tab-menu'>
  <a href="javascript:switchTab('%s', 'html')">HTML</a>
  <a href="javascript:switchTab('%s', 'text')">Text</a>
  <a href="javascript:switchTab('%s', 'tsv')">TSV</a>
</div>""" % (table, table, table)

  def GetReport(self):
    chart_javascript = ""
    charts = self._GetCharts(self.labels, self.benchmark_runs)
    for chart in charts:
      chart_javascript += chart.GetJavascript()
    chart_divs = ""
    for chart in charts:
      chart_divs += chart.GetDiv()

    summary_table = self.GetSummaryTables()
    full_table = self.GetFullTables()
    return self.HTML % (chart_javascript,
                        self.PrintTables(summary_table, "HTML"),
                        self.PrintTables(summary_table, "PLAIN"),
                        self.PrintTables(summary_table, "TSV"),
                        self._GetTabMenuHTML("summary"),
                        chart_divs,
                        self.PrintTables(full_table, "HTML"),
                        self.PrintTables(full_table, "PLAIN"),
                        self.PrintTables(full_table, "TSV"),
                        self._GetTabMenuHTML("full"),
                        self.experiment.experiment_file)

  def _GetCharts(self, labels, benchmark_runs):
    charts = []
    ro = ResultOrganizer(benchmark_runs, labels)
    result = ro.result
    for item in result:
      runs = result[item]
      tg = TableGenerator(runs, ro.labels)
      table = tg.GetTable()
      columns = [Column(AmeanResult(),
                        Format()),
                 Column(MinResult(),
                        Format()),
                 Column(MaxResult(),
                        Format())
                ]
      tf = TableFormatter(table, columns)
      data_table = tf.GetCellTable()

      for i in range(2, len(data_table)):
        cur_row_data = data_table[i]
        autotest_key = cur_row_data[0].string_value
        title = "{0}: {1}".format(item, autotest_key.replace("/", ""))
        chart = ColumnChart(title, 300, 200)
        chart.AddColumn("Label", "string")
        chart.AddColumn("Average", "number")
        chart.AddColumn("Min", "number")
        chart.AddColumn("Max", "number")
        chart.AddSeries("Min", "line", "black")
        chart.AddSeries("Max", "line", "black")
        cur_index = 1
        for label in ro.labels:
          chart.AddRow([label, cur_row_data[cur_index].value,
                        cur_row_data[cur_index + 1].value,
                        cur_row_data[cur_index + 2].value])
          if isinstance(cur_row_data[cur_index].value, str):
            chart = None
            break
          cur_index += 3
        if chart:
          charts.append(chart)
    return charts
