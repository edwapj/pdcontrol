"""
pdcontrol3.py
This program makes a loop that executes every 5 minutes.

It initially waits until the next half hourly period commences in order
to sychronise with National Electricity Market which works in
Australian Eastern Standard Time
It waits a further minute to allow for the communications delay
THe current prices are obtained and the control tasks are run.

The user's api_token and siteid for the Amber API can be entered
in the main program to obtain the current market prices
If these codes are not available the program will toggle the
output at each interval to test the radio link.

version 3 : made the AEST methods more readable.
          : changed the display of prices.
"""

import time
import csv
import json
import requests
from PiicoDev_Transceiver import PiicoDev_Transceiver
from PiicoDev_Unified import sleep_ms

class Aest:
    """class of Australian Eastern Standard Time functions"""
    def __init__(self):
        pass

    @staticmethod
    def get_aest_seconds():
        # get seconds since 00<00 1 Jan 1970
        epoch_seconds = time.time()
        # get AEST  (10hr timezone change GMT to AEST)
        aest_seconds = epoch_seconds + 10 * 3600
        return aest_seconds

    @staticmethod
    def get_aest_date():
        # get AEST  (10hr timezone change GMT to AEST)
        aest_seconds = Aest.get_aest_seconds()
        aest_date = time.asctime(time.gmtime(aest_seconds))
        return aest_date

    @staticmethod
    def get_day_no():
        # get day_no as decimal number
        aest_seconds = Aest.get_aest_seconds()
        day_no = aest_seconds/(24*60*60)
        return day_no

    @staticmethod
    def get_period_no():
        # get period_no       1 - 48 half hour periods in a day
        day_no = Aest.get_day_no()
        period_no = int((day_no % 1) * 48) + 1
        return period_no

    @staticmethod
    def get_sub_period_no():
        # get sub_period_no    1 - 6 five minute sub periods in a half hour
        day_no = Aest.get_day_no()
        period_no = Aest.get_period_no()
        sub_count = int((day_no % 1) * 48 * 6)
        sub_period_no = sub_count - (period_no-1) * 6 + 1
        return sub_period_no

    @staticmethod
    def get_sub_count():
        # get sub_count        0 - 288 completed sub periods since midnight
        day_no = Aest.get_day_no()
        sub_count = int((day_no % 1) * 48 * 6)
        return sub_count

    @staticmethod
    def get_delay(interval):
        # get seconds delay to next cardinal interval
        aest_seconds = Aest.get_aest_seconds()
        delay_seconds = interval - aest_seconds%interval
        return delay_seconds

    @staticmethod
    def get_time_range(period_no):
        # get time range for API request
        # range covers a day of 48 periods starting from 0000 hrs AEST
        # from (period_no - 1) to (48 -period_no) including Zero
        nextint = 48-period_no
        next = str(nextint)
        previousint = period_no - 1
        previous =   str(previousint)
        currentint = period_no
        current = str(currentint)
        time_range = "next="+next+"&"+"previous="+previous
        return time_range

class Datafile:
    def __init__(self, filename):
        pass

    @staticmethod
    def writefile(filename, datarow):
        with open(filename, mode='a',newline ='') as csv_file:
            operations_writer = csv.writer(csv_file, delimiter=',')
            operations_writer.writerow(datarow)

class Price:
    """class of electricity market price methods"""
    def __init__(self):
        pass

    @staticmethod
    def get_prices(range,aest_date,api_token,siteid):
        # obtains the half hourly electricty prices from the Amber Electric API

        # construct url string for the Amber API
        url = "https://api.amber.com.au/v1/sites/"+siteid+"/prices/current?"\
              +range+"&resolution=30"

        # construct header string
        headers = {'Content-Type': 'application/json', 'authorization' :\
            'Bearer ' + api_token}

        # call the Amber API
        response = requests.request("GET",url, headers = headers)
        try:
            # this method raises an exception if the request has failed
            response.raise_for_status()

        except requests.HTTPError() as err:
            # the except block executes if an exception has been raised
            print(f' err   {str(err)}')
            # Whoops it wasn't a 200
            strerror = str(err)
            print(f' strerror  {strerror[0:3]}')
            # if str(err[0:2]) == 403 :
            #     print(f' error is 403')
            print(f'error 1 in prices forecast_ls')
            # set the price forecast to default
            forecast_ls = [101,102,103,104,105,106,107,108,109]

            # write to error file
            error_row =[aest_date,forecast_ls]
            Datafile.writefile('pdcontrol3Err.csv', error_row )
            return forecast_ls

        # since there has been no exeception the excecution continues here

        # unpack serial string
        response_ls = response.json()

        forecast_ls = []
        if len(response_ls) >= 3 :
            for item in response_ls :
                forecast_ls.append(item['perKwh'])

            # write to data file (if required)
            if len(forecast_ls) > 5 :
                # use * operator to remove square brackets and commas from list
                datarow = [aest_date,*forecast_ls]
                Datafile.writefile('pdcontrol3Out.csv', datarow)
            return forecast_ls
        else :
            forecast_ls = [200,201,202,203,204,205,206,207,208]
            print(f'error 2 in prices forecast_ls {forecast_ls}')
            # write to error file
            error_row =[aest_date,forecast_ls]
            Datafile.writefile('pdcontrol3Err.csv', error_row )
        return forecast_ls

class Threshold:
    def __init__(self):
        pass

    @staticmethod
    def sort_forecast(forecast_ls):
        # sort prices in ascending order
        forecast_sorted_ls = sorted(forecast_ls)
        return forecast_sorted_ls

    @staticmethod
    def get_threshold_price(thres_index,forecast_sorted_ls):
        # get the threshold price corresponding to the given index

         # subtract one because array index starts from 0
        if len(forecast_sorted_ls) >= (thres_index - 1) :
            thres_price = forecast_sorted_ls[thres_index-1]
        else :
            # set an arbitrarily high price
            thres_price = 20000
        return thres_price

    @staticmethod
    def accumulate_ops(per_count,op_count,operate):
        # add any 5minute operation to the count for period
        # and add to the count for the day
        if operate == 1:
            per_count += 1
            op_count += 1
        return per_count, op_count

    @staticmethod
    def update_ops_ls(operations_ls,period_no,per_count):
        # update the operations count for latest period to the operations list

        # the list index is period_no less one since python lists start at zero
        operations_ls[period_no - 1] = per_count
        return operations_ls

    @staticmethod
    def reset_thres_index(op_count, thres_index_default):
        """raise threshold index if the actual operations for yesterday were
           less than the default.
            Index refers to a half hourly period
            convert 5minute count to half hour index and round up
        """
        # convert threshold 30 minute index to a 5 minute count
        thres_count_default = thres_index_default * 6

        if op_count <= thres_count_default :
            thres_count_new = 2 * thres_count_default - op_count
        else:
            thres_count_new = thres_count_default

        # convert from 5min count to half hour index
        thres_index = round(thres_count_new / 6)
        return thres_index

class Hws:
    def __init__(self):
        """attributes for class Remotehws"""

    @staticmethod
    def controller( price_now, thres_price):
        # controller decides when to operate
        if price_now <= thres_price :
            operate = 1
        else:
            operate = 0
        return operate

    @staticmethod
    def actuator(radio,operate):
        Hws.switch_piicodev(radio, operate)
        return operate

    @staticmethod
    def set_piicodev(radio):
        # initialise set_piicodev outputs.  Blink once for a test
        radio.send("Reset")
        sleep_ms(5000)
        radio.send("Set")
        sleep_ms(5000)
        radio.send("Reset")
        return

    @staticmethod
    def switch_piicodev(radio,operate):
        # operate piicodev outputs
        if operate == 1 :
            radio.send("Set")
        if operate == 0 :
            radio.send("Reset")
        return


class Action:
    def __init__(self):
        pass

    @staticmethod
    def sub_period_action(radio,aest_date,sub_count,period_no,sub_period_no,
            sub_interval,thres_index,thres_price,price_now,
            per_count,op_count):

        # get current time
        aest_date  = Aest.get_aest_date()

        # get controller
        operate = Hws.controller(price_now,thres_price)

        # get actuator
        operate = Hws.actuator(radio,operate)

        # increment ops count
        per_count,op_count = Threshold.accumulate_ops(per_count,op_count,
                                                        operate)

        datarow = [aest_date,period_no,thres_index,thres_price,price_now,
                   operate,per_count,op_count]
        Datafile.writefile('pdcontrol3dat.csv', datarow)

        return operate, per_count, op_count


def main():

    print(f' start of main program\n')

    # initialise variables
    # per_interval = 72        # 48 seconds for test
    # sub_interval = 32        #  16 seconds for test
    # comms_delay = 8          #  8 seconds for test

    per_interval = 1800        # 1800 seconds for half hour
    sub_interval = 300         #  300 seconds for five minutes
    comms_delay = 60           #   60 seconds for comms to update

    # set parameters for calling the API
    api_token = 'psk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
    siteid = 'XXXXXXXXXXXXXXXXXXXXXXXXXX'

    radio = PiicoDev_Transceiver()
    thres_index_default = 5  # set default threshold index
    thres_index = thres_index_default # initialise the threshold index .
    thres_price = 0  # initialise the threshold price to a high value
    operate = 0        # set operate switch to off.
    per_count = 0      # count of 5 minute operations in this 30 min period
    op_count = 0       # count of 5 minute operations in this day

    # create empty operations list
    operations_ls = [0] * 48

    print(f'initialise piico link')
    Hws.set_piicodev(radio)

    aest_date = Aest.get_aest_date()
    print(f'aest_date {aest_date}\n')

    # set wait time to next period
    seconds_delay = Aest.get_delay(per_interval)
    print(f'wait for next period {seconds_delay:.1f} seconds\n')
    time.sleep(seconds_delay)

    print(f'start of next period - wait for comms')

    # five minute loop
    while True:

        # get the nominal start date and time for this interval
        start_date  = Aest.get_aest_date()

        # sleep for comms_delay seconds
        time.sleep(comms_delay)

        # comms delay also removes any imprecision in the period calculations
        period_no = Aest.get_period_no()
        sub_period_no = Aest.get_sub_period_no()
        sub_count = Aest.get_sub_count()

        # If this is start of a new day
        if sub_count < 1 :

            # reset threshold Index
            thres_index = Threshold.reset_thres_index(op_count,
                                                  thres_index_default)

            # reset_operations_count
            op_count = 0

            # reset operations list
            operations_ls = [0] * 48

        # If this is the first sub_period of the next PERIOD
        if sub_period_no <= 1 :

            print(f' Do the tasks for this 30 minute Period \n\n')

            # #update the operations list for the previous period
            operations_ls = Threshold.update_ops_ls(operations_ls,
                                                    period_no,per_count)

            # reset period_count to zero for this period
            per_count = 0

            # get the time_range for this period
            time_range = Aest.get_time_range(period_no)

            if api_token == 'psk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' :

                # use dummy prices if no api_token
                forecast_ls = [18.57187, 17.53958, 17.01019,  5.55384,
                      5.46239,  4.75150,  5.03894, 4.798560,  5.51701,
                      5.56522,  5.98467,  6.0869,  6.22098,  17.54564,
                     15.4044,  17.89805, 22.61406 -1.16805,  19.31437,
                     15.90764, 16.48593,  1.63442, 1.35482,   1.23531,
                      1.17835,  1.08719,  0.67551, 0.49747,   0.51188,
                      0.67395,  1.59018, 17.04999,19.98452,  24.13931,
                     24.21063, 32.87613, 35.11841,36.35112,  36.39249,
                     35.11841, 35.80448, 36.42412,35.45605,  33.81102,
                     33.11331, 32.79671, 32.77451,33.6196]
            else :
                # get the forecast prices
                forecast_ls = Price.get_prices(time_range,
                                               aest_date,api_token,siteid)

            # sort forecast prices in ascending order
            forecast_sorted_ls = Threshold.sort_forecast(forecast_ls)

            print (f'operations list')
            op_ls = [ "%3d" % item for item in operations_ls]
            print(*op_ls)

            print (f'prices')
            fc_ls =  ["%3d" % round(num) for num in forecast_ls]
            print(*fc_ls)


            print (f'sorted prices')
            fs_ls =  ["%3d" % round(num) for num in forecast_sorted_ls]
            print(*fs_ls)

            # update threshold price
            thres_price  = Threshold.get_threshold_price(thres_index,
                                                         forecast_sorted_ls)

            print(f'\n threshold index {thres_index}'
                 f'    threshold price {thres_price}')

        # set time range for current price
        next = "1"
        previous =   "1"
        time_range = "next="+next+"&"+"previous="+previous

        # get market prices for periods -1,0,1

        if api_token == 'psk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' :
            # use dummy prices if no api_token
            if operate == 1:
                current_price_ls = [ 16.48593,  100, 1.35482]
            else :
                current_price_ls = [ 16.48593,  -1, 1.35482]
        else :
            # get the forecast prices
            current_price_ls = Price.get_prices(time_range,
                                                start_date,api_token,siteid)

        price_now = current_price_ls[1]

        # take control action for this sub period
        operate, per_count, op_count = Action.sub_period_action(radio,
                        start_date,sub_count,period_no,sub_period_no,
                        sub_interval,thres_index,thres_price,price_now,
                        per_count,op_count)

        print(f'\n PERIOD {period_no} SUB_PERIOD {sub_period_no} {start_date}'
              f'\n    thres_index {thres_index}   thres_price {thres_price}'
              f'  pricenow  {price_now}   opn {operate}'
              f'  percount  {per_count}   opcount {op_count}')

        seconds_delay = Aest.get_delay(sub_interval)
        print(f' wait for next sub period {seconds_delay:.1f} seconds \n')
        time.sleep(seconds_delay)

if __name__ == "__main__":

    main()

    print(f'End of run ')
