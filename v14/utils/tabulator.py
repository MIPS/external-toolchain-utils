#!/usr/bin/python

# Copyright 2011 Google Inc. All Rights Reserved.

import getpass
import math
import numpy

import colortrans
from email_sender import EmailSender
import misc


def _AllFloat(values):
  return all([misc.IsFloat(v) for v in values])


def _GetFloats(values):
  return [float(v) for v in values]


def _StripNone(results):
  res = []
  for result in results:
    if result is not None:
      res.append(result)
  return res


class TableGenerator(object):
  """Creates a table from a list of list of dicts.

  The main public function is called GetTable().
  """
  SORT_BY_KEYS = 0
  SORT_BY_KEYS_DESC = 1
  SORT_BY_VALUES = 2
  SORT_BY_VALUES_DESC = 3

  MISSING_VALUE = "x"

  def __init__(self, d, l, sort=SORT_BY_KEYS, key_name="keys"):
    self._runs = d
    self._labels = l
    self._sort = sort
    self._key_name = key_name

  def _AggregateKeys(self):
    keys = set([])
    for run_list in self._runs:
      for run in run_list:
        keys = keys.union(run.keys())
    return keys

  def _GetHighestValue(self, key):
    values = []
    for run_list in self._runs:
      for run in run_list:
        if key in run:
          values.append(run[key])
    ret = max(_StripNone(values))
    return ret

  def _GetLowestValue(self, key):
    values = []
    for run_list in self._runs:
      for run in run_list:
        if key in run:
          values.append(run[key])
    ret = min(_StripNone(values))
    return ret

  def _SortKeys(self, keys):
    if self._sort == self.SORT_BY_KEYS:
      return sorted(keys)
    elif self._sort == self.SORT_BY_VALUES:
      return sorted(keys, key=lambda x: self._GetLowestValue(x))
    elif self._sort == self.SORT_BY_VALUES_DESC:
      return sorted(keys, key=lambda x: self._GetHighestValue(x), reverse=True)
    else:
      assert 0, "Unimplemented sort %s" % self._sort

  def _GetKeys(self):
    keys = self._AggregateKeys()
    return self._SortKeys(keys)

  def GetTable(self):
    """Returns a table from a list of list of dicts.

    The list of list of dicts is passed into the constructor of TableGenerator.
    This method converts that into a canonical list of lists which represents a
    table of values.

    Args:
      None
    Returns:
      A list of lists which is the table.

    Example:
      We have the following runs:
        [[{"k1": "v1", "k2": "v2"}, {"k1": "v3"}],
         [{"k1": "v4", "k4": "v5"}]]
      and the following labels:
        ["vanilla", "modified"]
      it will return:
        [["Key", "vanilla", "modified"]
         ["k1", ["v1", "v3"], ["v4"]]
         ["k2", ["v2"], []]
         ["k4", [], ["v5"]]]
      The returned table can then be processed further by other classes in this
      module.
    """
    keys = self._GetKeys()
    header = [self._key_name] + self._labels
    table = [header]
    for k in keys:
      row = [k]
      for run_list in self._runs:
        v = []
        for run in run_list:
          if k in run:
            v.append(run[k])
          else:
            v.append(None)
        row.append(v)
      table.append(row)
    return table


class Result(object):
  """A class that respresents a single result.

  This single result is obtained by condensing the information from a list of
  runs and a list of baseline runs.
  """

  def __init__(self):
    pass

  def _AllStringsSame(self, values):
    values_set = set(values)
    return len(values_set) == 1

  def NeedsBaseline(self):
    return False

  def _Literal(self, cell, values, baseline_values):
    cell.value = " ".join([str(v) for v in values])

  def _ComputeFloat(self, cell, values, baseline_values):
    self._Literal(cell, values, baseline_values)

  def _ComputeString(self, cell, values, baseline_values):
    self._Literal(cell, values, baseline_values)

  def _InvertIfLowerIsBetter(self, cell):
    pass

  def _GetGmean(self, values):
    if not values:
      return float("nan")
    if any([v < 0 for v in values]):
      return float ("nan")
    if any([v == 0 for v in values]):
      return 0.0
    log_list = [math.log(v) for v in values]
    gmean_log = sum(log_list)/len(log_list)
    return math.exp(gmean_log)

  def Compute(self, cell, values, baseline_values):
    """Compute the result given a list of values and baseline values.

    Args:
      cell: A cell data structure to populate.
      values: List of values.
      baseline_values: List of baseline values. Can be none if this is the
      baseline itself.
    """
    all_floats = True
    values = _StripNone(values)
    if not len(values):
      cell.value = ""
      return
    if _AllFloat(values):
      float_values = _GetFloats(values)
    else:
      all_floats = False
    if baseline_values:
      baseline_values = _StripNone(baseline_values)
    if baseline_values:
      if _AllFloat(baseline_values):
        float_baseline_values = _GetFloats(baseline_values)
      else:
        all_floats = False
    else:
      if self.NeedsBaseline():
        cell.value = ""
        return
      float_baseline_values = None
    if all_floats:
      self._ComputeFloat(cell, float_values, float_baseline_values)
      self._InvertIfLowerIsBetter(cell)
    else:
      self._ComputeString(cell, values, baseline_values)


class LiteralResult(Result):
  def __init__(self, iteration=0):
    super(LiteralResult, self).__init__()
    self.iteration = iteration

  def Compute(self, cell, values, baseline_values):
    try:
      if values[self.iteration]:
        cell.value = values[self.iteration]
      else:
        cell.value = "-"
    except IndexError:
      cell.value = "-"


class NonEmptyCountResult(Result):
  def Compute(self, cell, values, baseline_values):
    cell.value = len(_StripNone(values))
    if not baseline_values:
      return
    base_value = len(_StripNone(baseline_values))
    if cell.value == base_value:
      return
    f = ColorBoxFormat()
    len_values = len(values)
    len_baseline_values = len(baseline_values)
    tmp_cell = Cell()
    tmp_cell.value= 1.0 + (float(cell.value - base_value) /
                         (max(len_values, len_baseline_values)))
    f.Compute(tmp_cell)
    cell.bgcolor = tmp_cell.bgcolor


class StringMeanResult(Result):
  def _ComputeString(self, cell, values, baseline_values):
    if self._AllStringsSame(values):
      cell.value = str(values[0])
    else:
      cell.value = "?"

class AmeanResult(StringMeanResult):
  def _ComputeFloat(self, cell, values, baseline_values):
    cell.value = numpy.mean(values)


class RawResult(Result):
  pass


class MinResult(Result):
  def _ComputeFloat(self, cell, values, baseline_values):
    cell.value = min(values)

  def _ComputeString(self, cell, values, baseline_values):
    if values:
      cell.value = min(values)
    else:
      cell.value = ""


class MaxResult(Result):
  def _ComputeFloat(self, cell, values, baseline_values):
    cell.value = max(values)

  def _ComputeString(self, cell, values, baseline_values):
    if values:
      cell.value = max(values)
    else:
      cell.value = ""


class NumericalResult(Result):
  def _ComputeString(self, cell, values, baseline_values):
    cell.value = "?"


class StdResult(NumericalResult):
  def _ComputeFloat(self, cell, values, baseline_values):
    cell.value = numpy.std(values)


class CoeffVarResult(NumericalResult):
  def _ComputeFloat(self, cell, values, baseline_values):
    noise = numpy.abs(numpy.std(values)/numpy.mean(values))
    cell.value = noise


class ComparisonResult(Result):
  def NeedsBaseline(self):
    return True

  def _ComputeString(self, cell, values, baseline_values):
    value = None
    baseline_value = None
    if self._AllStringsSame(values):
      value = values[0]
    if self._AllStringsSame(baseline_values):
      baseline_value = baseline_values[0]
    if value is not None and baseline_value is not None:
      if value == baseline_value:
        cell.value = "SAME"
      else:
        cell.value = "DIFFERENT"
    else:
      cell.value = "?"


class PValueResult(ComparisonResult):
  def _ComputeFloat(self, cell, values, baseline_values):
    if len(values) < 2 or len(baseline_values) < 2:
      cell.value = float("nan")
      return
    import stats
    _, cell.value = stats.lttest_ind(values, baseline_values)

  def _ComputeString(self, cell, values, baseline_values):
    return float("nan")


class KeyAwareComparisonResult(ComparisonResult):
  def _IsLowerBetter(self, key):
    lower_is_better_keys = ["milliseconds", "ms", "seconds", "KB",
                            "rdbytes", "wrbytes"]
    return any([key.startswith(l + "_") for l in lower_is_better_keys])

  def _InvertIfLowerIsBetter(self, cell):
    if self._IsLowerBetter(cell.name):
      if cell.value:
        cell.value = 1.0/cell.value


class AmeanRatioResult(KeyAwareComparisonResult):
  def _ComputeFloat(self, cell, values, baseline_values):
    if numpy.mean(baseline_values) != 0:
      cell.value = numpy.mean(values)/numpy.mean(baseline_values)
    elif numpy.mean(values) != 0:
      cell.value = 0.00
      # cell.value = 0 means the values and baseline_values have big difference
    else:
      cell.value = 1.00
      # no difference if both values and baseline_values are 0


class GmeanRatioResult(KeyAwareComparisonResult):
  def _ComputeFloat(self, cell, values, baseline_values):
    if self._GetGmean(baseline_values) != 0:
      cell.value = self._GetGmean(values)/self._GetGmean(baseline_values)
    elif self._GetGmean(values) != 0:
      cell.value = 0.00
    else:
      cell.value = 1.00


class Color(object):
  """Class that represents color in RGBA format."""

  def __init__(self, r=0, g=0, b=0, a=0):
    self.r = r
    self.g = g
    self.b = b
    self.a = a

  def __str__(self):
    return "r: %s g: %s: b: %s: a: %s" % (self.r, self.g, self.b, self.a)

  def Round(self):
    """Round RGBA values to the nearest integer."""
    self.r = int(self.r)
    self.g = int(self.g)
    self.b = int(self.b)
    self.a = int(self.a)

  def GetRGB(self):
    """Get a hex representation of the color."""
    return "%02x%02x%02x" % (self.r, self.g, self.b)

  @classmethod
  def Lerp(cls, ratio, a, b):
    """Perform linear interpolation between two colors.

    Args:
      ratio: The ratio to use for linear polation.
      a: The first color object (used when ratio is 0).
      b: The second color object (used when ratio is 1).

    Returns:
      Linearly interpolated color.
    """
    ret = cls()
    ret.r = (b.r - a.r)*ratio + a.r
    ret.g = (b.g - a.g)*ratio + a.g
    ret.b = (b.b - a.b)*ratio + a.b
    ret.a = (b.a - a.a)*ratio + a.a
    return ret


class Format(object):
  """A class that represents the format of a column."""

  def __init__(self):
    pass

  def Compute(self, cell):
    """Computes the attributes of a cell based on its value.

    Attributes typically are color, width, etc.

    Args:
      cell: The cell whose attributes are to be populated.
    """
    if cell.value is None:
      cell.string_value = ""
    if isinstance(cell.value, float):
      self._ComputeFloat(cell)
    else:
      self._ComputeString(cell)

  def _ComputeFloat(self, cell):
    cell.string_value = "{0:.2f}".format(cell.value)

  def _ComputeString(self, cell):
    cell.string_value = str(cell.value)

  def _GetColor(self, value, low, mid, high, power=6, mid_value=1.0):
    min_value = 0.0
    max_value = 2.0
    if math.isnan(value):
      return mid
    if value > mid_value:
      value = max_value - mid_value/value

    return self._GetColorBetweenRange(value, min_value, mid_value, max_value,
                                      low, mid, high, power)

  def _GetColorBetweenRange(self,
                            value,
                            min_value, mid_value, max_value,
                            low_color, mid_color, high_color,
                            power):
    assert value <= max_value
    assert value >= min_value
    if value > mid_value:
      value = (max_value - value)/(max_value - mid_value)
      value **= power
      ret = Color.Lerp(value, high_color, mid_color)
    else:
      value = (value - min_value)/(mid_value - min_value)
      value **= power
      ret = Color.Lerp(value, low_color, mid_color)
    ret.Round()
    return ret


class PValueFormat(Format):
  def _ComputeFloat(self, cell):
    cell.string_value = "%0.2f" % float(cell.value)
    if float(cell.value) < 0.05:
      cell.bgcolor = self._GetColor(cell.value,
                                  Color(255, 255, 0, 0),
                                  Color(255, 255, 255, 0),
                                  Color(255, 255, 255, 0),
                                  mid_value=0.05,
                                  power=1)
      cell.bgcolor_row = True


class StorageFormat(Format):
  """Format the cell as a storage number.

  Example:
    If the cell contains a value of 1024, the string_value will be 1.0K.
  """

  def _ComputeFloat(self, cell):
    base = 1024
    suffices = ["K", "M", "G"]
    v = float(cell.value)
    current = 0
    while v >= base**(current + 1) and current < len(suffices):
      current += 1

    if current:
      divisor = base**current
      cell.string_value = "%1.1f%s" % ((v/divisor), suffices[current - 1])
    else:
      cell.string_value = str(cell.value)


class CoeffVarFormat(Format):
  """Format the cell as a percent.

  Example:
    If the cell contains a value of 1.5, the string_value will be +150%.
  """

  def _ComputeFloat(self, cell):
    cell.string_value = "%1.1f%%" % (float(cell.value) * 100)
    cell.color = self._GetColor(cell.value,
                                Color(0, 255, 0, 0),
                                Color(0, 0, 0, 0),
                                Color(255, 0, 0, 0),
                                mid_value=0.02,
                                power=1)


class PercentFormat(Format):
  """Format the cell as a percent.

  Example:
    If the cell contains a value of 1.5, the string_value will be +50%.
  """

  def _ComputeFloat(self, cell):
    cell.string_value = "%+1.1f%%" % ((float(cell.value) - 1) * 100)
    cell.color = self._GetColor(cell.value,
                                Color(255, 0, 0, 0),
                                Color(0, 0, 0, 0),
                                Color(0, 255, 0, 0))


class RatioFormat(Format):
  """Format the cell as a ratio.

  Example:
    If the cell contains a value of 1.5642, the string_value will be 1.56.
  """

  def _ComputeFloat(self, cell):
    cell.string_value = "%+1.1f%%" % ((cell.value - 1) * 100)
    cell.color = self._GetColor(cell.value,
                                Color(255, 0, 0, 0),
                                Color(0, 0, 0, 0),
                                Color(0, 255, 0, 0))


class ColorBoxFormat(Format):
  """Format the cell as a color box.

  Example:
    If the cell contains a value of 1.5, it will get a green color.
    If the cell contains a value of 0.5, it will get a red color.
    The intensity of the green/red will be determined by how much above or below
    1.0 the value is.
  """

  def _ComputeFloat(self, cell):
    cell.string_value = "--"
    bgcolor = self._GetColor(cell.value,
                             Color(255, 0, 0, 0),
                             Color(255, 255, 255, 0),
                             Color(0, 255, 0, 0))
    cell.bgcolor = bgcolor
    cell.color = bgcolor


class Cell(object):
  """A class to represent a cell in a table.

  Attributes:
    value: The raw value of the cell.
    color: The color of the cell.
    bgcolor: The background color of the cell.
    string_value: The string value of the cell.
    suffix: A string suffix to be attached to the value when displaying.
    prefix: A string prefix to be attached to the value when displaying.
    color_row: Indicates whether the whole row is to inherit this cell's color.
    bgcolor_row: Indicates whether the whole row is to inherit this cell's
    bgcolor.
    width: Optional specifier to make a column narrower than the usual width.
    The usual width of a column is the max of all its cells widths.
    colspan: Set the colspan of the cell in the HTML table, this is used for
    table headers. Default value is 1.
    name: the test name of the cell.
  """

  def __init__(self):
    self.value = None
    self.color = None
    self.bgcolor = None
    self.string_value = None
    self.suffix = None
    self.prefix = None
    # Entire row inherits this color.
    self.color_row = False
    self.bgcolor_row = False
    self.width = None
    self.colspan = 1
    self.name = None

  def __str__(self):
    l = []
    l.append("value: %s" % self.value)
    l.append("string_value: %s" % self.string_value)
    return " ".join(l)


class Column(object):
  """Class representing a column in a table.

  Attributes:
    result: an object of the Result class.
    fmt: an object of the Format class.
  """

  def __init__(self, result, fmt, name=""):
    self.result = result
    self.fmt = fmt
    self.name = name


# Takes in:
# ["Key", "Label1", "Label2"]
# ["k", ["v", "v2"], [v3]]
# etc.
# Also takes in a format string.
# Returns a table like:
# ["Key", "Label1", "Label2"]
# ["k", avg("v", "v2"), stddev("v", "v2"), etc.]]
# according to format string
class TableFormatter(object):
  """Class to convert a plain table into a cell-table.

  This class takes in a table generated by TableGenerator and a list of column
  formats to apply to the table and returns a table of cells.
  """

  def __init__(self, table, columns):
    """The constructor takes in a table and a list of columns.

    Args:
      table: A list of lists of values.
      columns: A list of column containing what to produce and how to format it.
    """
    self._table = table
    self._columns = columns
    self._table_columns = []
    self._out_table = []

  def _GenerateCellTable(self):
    row_index = 0

    for row in self._table[1:]:
      key = Cell()
      key.string_value = str(row[0])
      out_row = [key]
      baseline = None
      for values in row[1:]:
        for column in self._columns:
          cell = Cell()
          cell.name = key.string_value
          if column.result.NeedsBaseline():
            if baseline is not None:
              column.result.Compute(cell, values, baseline)
              column.fmt.Compute(cell)
              out_row.append(cell)
              if not row_index:
                self._table_columns.append(column)
          else:
            column.result.Compute(cell, values, baseline)
            column.fmt.Compute(cell)
            out_row.append(cell)
            if not row_index:
              self._table_columns.append(column)

        if baseline is None:
          baseline = values
      self._out_table.append(out_row)
      row_index += 1

    # TODO(asharif): refactor this.
    # Now generate header
    key = Cell()
    key.string_value = "Keys"
    header = [key]
    for column in self._table_columns:
      cell = Cell()
      if column.name:
        cell.string_value = column.name
      else:
        result_name = column.result.__class__.__name__
        format_name = column.fmt.__class__.__name__

        cell.string_value = "%s %s" % (result_name.replace("Result", ""),
                                       format_name.replace("Format", ""))

      header.append(cell)

    self._out_table = [header] + self._out_table

    top_header = []
    colspan = 0
    for column in self._columns:
      if not column.result.NeedsBaseline():
        colspan += 1
    for label in self._table[0]:
      cell = Cell()
      cell.string_value = str(label)
      if cell.string_value != "keys":
        cell.colspan = colspan
      top_header.append(cell)

    self._out_table = [top_header] + self._out_table

    return self._out_table

  def _PrintOutTable(self):
    o = ""
    for row in self._out_table:
      for cell in row:
        o += str(cell) + " "
      o += "\n"
    print o

  def GetCellTable(self):
    """Function to return a table of cells.

    The table (list of lists) is converted into a table of cells by this
    function.

    Returns:
      A table of cells with each cell having the properties and string values as
      requiested by the columns passed in the constructor.
    """
    # Generate the cell table, creating a list of dynamic columns on the fly.
    return self._GenerateCellTable()


class TablePrinter(object):
  """Class to print a cell table to the console, file or html."""
  PLAIN = 0
  CONSOLE = 1
  HTML = 2
  TSV = 3
  EMAIL = 4

  def __init__(self, table, output_type):
    """Constructor that stores the cell table and output type."""
    self._table = table
    self._output_type = output_type

  # Compute whole-table properties like max-size, etc.
  def _ComputeStyle(self):
    self._row_styles = []
    for row in self._table:
      row_style = Cell()
      for cell in row:
        if cell.color_row:
          assert cell.color, "Cell color not set but color_row set!"
          assert not row_style.color, "Multiple row_style.colors found!"
          row_style.color = cell.color
        if cell.bgcolor_row:
          assert cell.bgcolor, "Cell bgcolor not set but bgcolor_row set!"
          assert not row_style.bgcolor, "Multiple row_style.bgcolors found!"
          row_style.bgcolor = cell.bgcolor
      self._row_styles.append(row_style)

    self._column_styles = []
    if len(self._table) < 2:
      return
    for i in range(len(self._table[1])):
      column_style = Cell()
      for row in self._table[1:]:
        column_style.width = max(column_style.width,
                                 len(row[i].string_value))
      self._column_styles.append(column_style)

  def _GetBGColorFix(self, color):
    if self._output_type == self.CONSOLE:
      rgb = color.GetRGB()
      prefix, _ = colortrans.rgb2short(rgb)
      prefix = "\033[48;5;%sm" % prefix
      suffix = "\033[0m"
    elif self._output_type in [self.EMAIL, self.HTML]:
      rgb = color.GetRGB()
      prefix = ("<FONT style=\"BACKGROUND-COLOR:#{0}\">"
                .format(rgb))
      suffix = "</FONT>"
    elif self._output_type in [self.PLAIN, self.TSV]:
      prefix = ""
      suffix = ""
    return prefix, suffix

  def _GetColorFix(self, color):
    if self._output_type == self.CONSOLE:
      rgb = color.GetRGB()
      prefix, _ = colortrans.rgb2short(rgb)
      prefix = "\033[38;5;%sm" % prefix
      suffix = "\033[0m"
    elif self._output_type in [self.EMAIL, self.HTML]:
      rgb = color.GetRGB()
      prefix = "<FONT COLOR=#{0}>".format(rgb)
      suffix = "</FONT>"
    elif self._output_type in [self.PLAIN, self.TSV]:
      prefix = ""
      suffix = ""
    return prefix, suffix

  def Print(self):
    """Print the table to a console, html, etc.

    Returns:
      A string that contains the desired representation of the table.
    """
    self._ComputeStyle()
    return self._GetStringValue()

  def _GetCellValue(self, i, j):
    cell = self._table[i][j]
    out = cell.string_value
    raw_width = len(out)

    if cell.color:
      p, s = self._GetColorFix(cell.color)
      out = "%s%s%s" % (p, out, s)

    if cell.bgcolor:
      p, s = self._GetBGColorFix(cell.bgcolor)
      out = "%s%s%s" % (p, out, s)

    if self._output_type in [self.PLAIN, self.CONSOLE, self.EMAIL]:
      if cell.width:
        width = cell.width
      else:
        if self._column_styles:
          width = self._column_styles[j].width
        else:
          width = len(cell.string_value)
      if cell.colspan > 1:
        width = 0
        for k in range(cell.colspan):
          width += self._column_styles[1 + (j-1) * cell.colspan + k].width
      if width > raw_width:
        padding = ("%" + str(width - raw_width) + "s") % ""
        out = padding + out

    if self._output_type == self.HTML:
      if i < 2:
        tag = "th"
      else:
        tag = "td"
      out = "<{0} colspan = \"{2}\"> {1} </{0}>".format(tag, out, cell.colspan)

    return out

  def _GetHorizontalSeparator(self):
    if self._output_type in [self.CONSOLE, self.PLAIN, self.EMAIL]:
      return " "
    if self._output_type == self.HTML:
      return ""
    if self._output_type == self.TSV:
      return "\t"

  def _GetVerticalSeparator(self):
    if self._output_type in [self.PLAIN, self.CONSOLE, self.TSV, self.EMAIL]:
      return "\n"
    if self._output_type == self.HTML:
      return "</tr>\n<tr>"

  def _GetPrefix(self):
    if self._output_type in [self.PLAIN, self.CONSOLE, self.TSV, self.EMAIL]:
      return ""
    if self._output_type == self.HTML:
      return "<p></p><table id=\"box-table-a\">\n<tr>"

  def _GetSuffix(self):
    if self._output_type in [self.PLAIN, self.CONSOLE, self.TSV, self.EMAIL]:
      return ""
    if self._output_type == self.HTML:
      return "</tr>\n</table>"

  def _GetStringValue(self):
    o = ""
    o += self._GetPrefix()
    for i in range(len(self._table)):
      row = self._table[i]
      # Apply row color and bgcolor.
      p = s = bgp = bgs = ""
      if self._row_styles[i].bgcolor:
        bgp, bgs = self._GetBGColorFix(self._row_styles[i].bgcolor)
      if self._row_styles[i].color:
        p, s = self._GetColorFix(self._row_styles[i].color)
      o += p + bgp
      for j in range(len(row)):
        out = self._GetCellValue(i, j)
        o += out + self._GetHorizontalSeparator()
      o += s + bgs
      o += self._GetVerticalSeparator()
    o += self._GetSuffix()
    return o


# Some common drivers
def GetSimpleTable(table, out_to=TablePrinter.CONSOLE):
  """Prints a simple table.

  This is used by code that has a very simple list-of-lists and wants to produce
  a table with ameans, a percentage ratio of ameans and a colorbox.

  Args:
    table: a list of lists.
    out_to: specify the fomat of output. Currently it supports HTML and CONSOLE.

  Returns:
    A string version of the table that can be printed to the console.

  Example:
    GetSimpleConsoleTable([["binary", "b1", "b2"],["size", "300", "400"]])
    will produce a colored table that can be printed to the console.
  """
  columns = [
      Column(AmeanResult(),
             Format()),
      Column(AmeanRatioResult(),
             PercentFormat()),
      Column(AmeanRatioResult(),
             ColorBoxFormat()),
      ]
  our_table = [table[0]]
  for row in table[1:]:
    our_row = [row[0]]
    for v in row[1:]:
      our_row.append([v])
    our_table.append(our_row)

  tf = TableFormatter(our_table, columns)
  cell_table = tf.GetCellTable()
  tp = TablePrinter(cell_table, out_to)
  return tp.Print()


def GetComplexTable(runs, labels, out_to=TablePrinter.CONSOLE):
  tg = TableGenerator(runs, labels, TableGenerator.SORT_BY_VALUES_DESC)
  table = tg.GetTable()
  columns = [Column(LiteralResult(),
                    Format(),
                    "Literal"),
             Column(AmeanResult(),
                    Format()),
             Column(StdResult(),
                    Format()),
             Column(CoeffVarResult(),
                    CoeffVarFormat()),
             Column(NonEmptyCountResult(),
                    Format()),
             Column(AmeanRatioResult(),
                    PercentFormat()),
             Column(AmeanRatioResult(),
                    RatioFormat()),
             Column(GmeanRatioResult(),
                    RatioFormat()),
             Column(PValueResult(),
                    PValueFormat()),
            ]
  tf = TableFormatter(table, columns)
  cell_table = tf.GetCellTable()
  tp = TablePrinter(cell_table, out_to)
  return tp.Print()

if __name__ == "__main__":
  # Run a few small tests here.
  runs = [
      [
          {"k1": "10", "k2": "12", "k5": "40", "k6": "40",
           "ms_1": "20", "k7": "FAIL", "k8": "PASS", "k9": "PASS",
           "k10": "0"},
          {"k1": "13", "k2": "14", "k3": "15", "ms_1": "10", "k8": "PASS",
           "k9": "FAIL", "k10": "0"}
          ],
      [
          {"k1": "50", "k2": "51", "k3": "52", "k4": "53", "k5": "35", "k6":
           "45", "ms_1": "200", "ms_2": "20", "k7": "FAIL", "k8": "PASS", "k9":
           "PASS"},
          ],
      ]
  labels = ["vanilla", "modified"]
  t = GetComplexTable(runs, labels, TablePrinter.CONSOLE)
  print t
  email = GetComplexTable(runs, labels, TablePrinter.EMAIL)

  runs = [
      [
          {"k1": "1",}, {"k1": "1.1"}, {"k1": "1.2"},
          ],
      [
          {"k1": "5",}, {"k1": "5.1"}, {"k1": "5.2"},
          ],
      ]
  t = GetComplexTable(runs, labels, TablePrinter.CONSOLE)
  print t

  simple_table = [
      ["binary", "b1", "b2", "b3"],
      ["size", 100, 105, 108],
      ["rodata", 100, 80, 70],
      ["data", 100, 100, 100],
      ["debug", 100, 140, 60],
      ]
  t = GetSimpleTable(simple_table)
  print t
  email += GetSimpleTable(simple_table, TablePrinter.HTML)
  email_to = [getpass.getuser()]
  email = "<pre style='font-size: 13px'>%s</pre>" % email
  EmailSender().SendEmail(email_to, "SimpleTableTest", email, msg_type="html")
