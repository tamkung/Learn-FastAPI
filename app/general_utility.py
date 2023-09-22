import datetime
import time as time_lib
import email.utils
import pytz
from datetime import timedelta, datetime, time
from dateutil.parser import parse

def convert_timestamp_in_datetime_utc(timestamp_received):
    dt_naive_utc = datetime.utcfromtimestamp(timestamp_received)
    return dt_naive_utc.replace(tzinfo=pytz.utc)

def convertStrToDate(time):
    try:
        if isinstance(int(time), int):
            return int(time)
    except:
        pass
    try:
        if isinstance(float(time), float):
            return float(time)
    except:
        pass
    try:
        result = datetime.strptime(str(time), "%Y-%m-%d %H:%M:%S.%f")
    except:
        try:
            result = datetime.strptime(str(time), "%Y-%m-%d %H:%M:%S")
        except:
            try:
                result = datetime.strptime(str(time), "%Y-%m-%dT%H:%M:%SZ")
            except:
                try:
                    result = datetime.strptime(str(time), "%Y-%m-%dT%H:%M:%S")
                except:
                    try:
                        result = datetime.strptime(str(time), "%Y-%m-%dT%H:%M:%S.%f")
                    except:
                        try:
                            result = parse(str(time))
                        except:
                            result = email.utils.parsedate(str(time))
                            result = convert_timestamp_in_datetime_utc(
                                time_lib.mktime(result)
                            )
                            result = result - timedelta(hours=7)

    return result

