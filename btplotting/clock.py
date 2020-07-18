import bisect

from datetime import datetime

import pandas as pd
import backtrader as bt


def get_slice_with_end(data, start, end):
    # end smaller than start will occur if arr is empty
    if end >= start:
        # get slice + value at end pos
        slice = list(data)[start:end] + [data[end]]
    else:
        slice = []
    return slice


class ClockGenerator:

    '''
    ClockGenerator will wrap a datetime line and returns clock values

    This class is used to generate a clock values which can be used with
    the ClockHandler.

    The clock values list is generated by calling get_clock. This will
    return an array with dates and the start and end index values
    matching the positions of the dates of the returned array.

    Note: the end value is increased by 1 so when slicing a line, the last
    item is included.
    '''

    def __init__(self, strategy, dataname=False):
        clk, tz = self._get_clock_values(strategy, dataname)
        self._clk = clk
        self._tz = tz

    def _get_clock_values(self, strategy, dataname):
        '''
        Returns clock values (clk, tz)
        '''
        if dataname is not False:
            data = strategy.getdatabyname(dataname)
            return data.datetime, data._tz
        # if no dataname provided, use first data
        return strategy.data.datetime, strategy.data._tz

    def _get_clock_array(self):
        '''
        Generates a list with dates by converting the float datetime value
        using the tz info
        '''
        # don't include nan in here by checking for x == x
        # this happens for live data with rows that are not filled yet
        clk_arr = [bt.num2date(x, self._tz) for x in self._clk.array if x == x]
        return clk_arr

    def _get_clock_range(self, arr, start=None, end=None, back=None):
        '''
        Returns the range (start, end)
        '''
        if start is None:
            start = 0
        elif type(start) == datetime:
            start = bisect.bisect_left(arr, start)
        if end is None:
            end = len(arr) - 1
        elif type(end) == datetime:
            # set pos of end to pos - 1 to match usage in other parts
            end = bisect.bisect_right(arr, end) - 1
        # if back is provided, move back from end, override start
        if back:
            # prevent negative start int, add one
            # since when collecting data, end will
            # be included
            start = max(0, end - back + 1)
        return start, end

    def get_clock(self, start=None, end=None, back=None):
        '''
        Returns clock values for given start, end and back values

        If no start and no end is provided, the whole clock will be
        returned.
        If back is provided, then start will be overriden.
        '''
        arr = self._get_clock_array()
        start, end = self._get_clock_range(arr, start, end, back)
        arr = get_slice_with_end(arr, start, end)
        return arr, start, end


class ClockHandler:

    '''
    ClockHandler will generate a slice of data

    It is using a clock generated by ClockGenerator and align the data
    to another clock.
    '''

    def __init__(self, clk, start, end):
        self.clk = clk
        self.start = start
        self.end = end

    def _get_data_from_list(self, llist, clk):
        '''
        Generates data based on given clock
        '''
        data = []
        c_idx = 0
        for c in clk:
            sc_prev = None
            v = float('nan')
            for sc_idx in range(c_idx, len(llist)):
                sc = self.clk[sc_idx]
                # match source clock (sc) on target clock by direct hit
                if sc == c:
                    # store current value and remember source clock
                    # position for next iteration (c_idx)
                    v = llist[sc_idx]
                    c_idx = sc_idx + 1
                    break
                # match source clock (sc) on passing boundry of
                # target clock (c)
                elif (sc_prev and sc_prev < c and sc > c):
                    # get last value, current value is already on new clock pos
                    v = llist[sc_idx - 1]
                    c_idx = sc_idx
                    break
                elif sc > c:
                    break
                sc_prev = sc
            data.append(v)

        return data

    def get_list_from_line(self, line, clkalign=None):
        '''
        Returns a list with values from the given line values
        aligned to the given clock list
        '''
        start = max(0, self.start)
        end = min(len(line) - 1, self.end)
        llist = get_slice_with_end(line.array, start, end)

        if clkalign is None:
            clkalign = self.clk
        data = self._get_data_from_list(llist, clkalign)
        return data

    def get_df_from_series(self, series, clkalign=None, name_prefix=""):
        '''
        Returns a DataFrame from the given LineSeries
        The column names will use the name_prefix and the line alias
        '''
        df = pd.DataFrame()
        for lineidx in range(series.size()):
            linealias = series.lines._getlinealias(lineidx)
            if linealias == 'datetime':
                continue
            line = series.lines[lineidx]
            df[name_prefix + linealias] = self.get_list_from_line(
                line, clkalign)
        return df
