#! usr/bin/python
#coding=utf-8
"""
中国节假日
版本：0.1.1
"""
from homeassistant.helpers.entity import Entity
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import event as evt
import voluptuous as vol
import logging
from homeassistant.util import Throttle
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
     CONF_NAME)
from homeassistant.helpers.entity import generate_entity_id
import datetime
from datetime import timedelta
import time
from . import holiday
from . import lunar

_LOGGER = logging.getLogger(__name__)

"""
    cal = lunar.CalendarToday()
    print(cal.solar_Term())
    print(cal.festival_description())
    print(cal.solar_date_description())
    print(cal.week_description())
    print(cal.lunar_date_description())
    print(cal.solar())
    print(cal.lunar())
"""

_Log=logging.getLogger(__name__)

DEFAULT_NAME = 'chinese_holiday'
CONF_UPDATE_INTERVAL = 'update_interval'
CONF_SOLAR_ANNIVERSARY = 'solar_anniversary'
CONF_LUNAR_ANNIVERSARY = 'lunar_anniversary'
CONF_CALCULATE_AGE = 'calculate_age'
CONF_CALCULATE_AGE_DATE = 'date'
CONF_CALCULATE_AGE_NAME = 'name'
CONF_NOTIFY_SCRIPT_NAME = 'notify_script_name'
CONF_NOTIFY_PRINCIPLES = 'notify_principles'

# CALCULATE_AGE_DEFAULTS_SCHEMA = vol.Any(None, vol.Schema({
#     vol.Optional(CONF_TRACK_NEW, default=DEFAULT_TRACK_NEW): cv.boolean,
#     vol.Optional(CONF_AWAY_HIDE, default=DEFAULT_AWAY_HIDE): cv.boolean,
# }))

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NOTIFY_SCRIPT_NAME, default=''): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SOLAR_ANNIVERSARY, default={}): dict,
    vol.Optional(CONF_LUNAR_ANNIVERSARY, default={}): dict,
    vol.Optional(CONF_CALCULATE_AGE,default=[]): [
        {
            vol.Optional(CONF_CALCULATE_AGE_DATE): cv.string,
            vol.Optional(CONF_CALCULATE_AGE_NAME): cv.string,
        }
    ],
    vol.Optional(CONF_NOTIFY_PRINCIPLES,default={}): dict,
    vol.Optional(CONF_UPDATE_INTERVAL, default=timedelta(seconds=1)): (vol.All(cv.time_period, cv.positive_timedelta)),
})


#公历 纪念日 每年都有的
# {'0101':['aa生日','bb生日']}
SOLAR_ANNIVERSARY = {}

#农历 纪念日 每年都有的
# {'0101':['aa生日','bb生日']}
LUNAR_ANNIVERSARY = {}

#纪念日 指定时间的（出生日到今天的计时或今天到某一天还需要的时间例如金婚）
CALCULATE_AGE = {}

NOTIFY_PRINCIPLES = {}
    # '2010-10-10 08:23:12': 'xx',

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the movie sensor."""

    name = config[CONF_NAME]
    interval = config.get(CONF_UPDATE_INTERVAL)
    global SOLAR_ANNIVERSARY
    global LUNAR_ANNIVERSARY
    global CALCULATE_AGE
    global NOTIFY_PRINCIPLES
    SOLAR_ANNIVERSARY = config[CONF_SOLAR_ANNIVERSARY]
    LUNAR_ANNIVERSARY = config[CONF_LUNAR_ANNIVERSARY]
    CALCULATE_AGE = config[CONF_CALCULATE_AGE]
    NOTIFY_PRINCIPLES = config[CONF_NOTIFY_PRINCIPLES]
    script_name = config[CONF_NOTIFY_SCRIPT_NAME]
    sensors = [ChineseHolidaySensor(hass, name,script_name, interval)]
    add_devices(sensors, True)


class ChineseHolidaySensor(Entity):

    _holiday = None
    _lunar = None

    def __init__(self, hass, name,script_name, interval):
        """Initialize the sensor."""
        self.client_name = name
        self._state = None
        self._hass = hass
        self._script_name = script_name
        self._holiday = holiday.Holiday()
        self._lunar = lunar.CalendarToday()
        self.attributes = {}
        self.entity_id = generate_entity_id(
            'sensor.{}', self.client_name, hass=self._hass)
        self.update = Throttle(interval)(self._update)
        self.setListener() #设置脚本通知的定时器

    @property
    def name(self):
        """Return the name of the sensor."""
        return '节假日'

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return 'mdi:calendar-today'

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self.attributes

    def setListener(self):

        async def _date_listener_callback(_):
            _LOGGER.info('_date_listener_callback')
            self.setListener() #重设定时器
            self.notify() #执行通知

        # self._listener = None
        # now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        now = datetime.datetime.utcnow() + timedelta(hours=8)
        notify_date_str = now.strftime('%Y-%m-%d') + ' 12:00:00' #目前预设是每天9点通知
        notify_date = datetime.datetime.strptime(notify_date_str, "%Y-%m-%d %H:%M:%S")
        _LOGGER.error('now')
        _LOGGER.error(now)
        if notify_date < now:
            _LOGGER.error('小于')
            notify_date = notify_date + timedelta(days=1) #已经过了就设置为明天的时间
        _LOGGER.error('notify_date')
        _LOGGER.error(notify_date)
        evt.async_track_point_in_time(
            self._hass, _date_listener_callback, notify_date
        )



    def notify(self):
        #[{'days':1,'list':['国庆节']}]
        def dates_need_to_notify():
            """
                {
                 '14|7|1':[{'date':'0101','solar':True}]
                }
            """
            dates = []
            for key,value in NOTIFY_PRINCIPLES.items():
                days = key.split('|') #解析需要匹配的天 14|7|1 分别还有14，7，1天时推送
                for item in value:
                    date = item['date'] #0101 格式的日期字符串
                    solar = item['solar'] #是否是公历
                    fes_date = None
                    fes_list = []
                    if solar:
                        date_str = str(self._lunar.solar()[0])+date #20200101
                        fes_date = datetime.datetime.strptime(date_str,'%Y%m%d')
                        try:
                            fes_list = lunar.Festival._solar_festival[date]
                        except Exception as e:
                            pass
                        try:
                            fes_list += SOLAR_ANNIVERSARY[date]
                        except Exception as e:
                            pass
                    else:
                        month = int(date[:2])
                        day = int(date[2:])
                        fes_date = lunar.CalendarToday.lunar_to_solar(self._lunar.solar()[0],month,day)#下标和位置
                        try:
                            fes_list = lunar.Festival._lunar_festival[date]
                        except Exception as e:
                            pass
                        try:
                            fes_list += LUNAR_ANNIVERSARY[date]
                        except Exception as e:
                            pass

                    now_str = datetime.datetime.now().strftime('%Y-%m-%d')
                    today = datetime.datetime.strptime(now_str, "%Y-%m-%d")
                    diff = (fes_date - today).days
                    if (str(diff) in days) and fes_list:
                        item['day'] = diff
                        item['list'] = fes_list
                        dates.append(item)
            return dates

        if self._script_name and NOTIFY_PRINCIPLES:
            dates = dates_need_to_notify()
            _LOGGER.info(dates)
            messages = []
            for item in dates:
                days = item['day']
                fes_list = item['list']
                messages.append('距离 ' + ','.join(fes_list) + '还有' + str(days) + '天')
            self._hass.services.call('script',self._script_name,{'message':','.join(messages)})

    #计算纪念日（每年都有的）
    def calculate_anniversary(self):
        def anniversary_handle(list):
            return ','.join(list)
        """
            {
                '20200101':[{'anniversary':'0101#xx生日#','solar':True}]
            }
        """
        anniversaries = {}

        for key,value in LUNAR_ANNIVERSARY.items():
            month = int(key[:2])
            day = int(key[2:])
            solar_date = lunar.CalendarToday.lunar_to_solar(self._lunar.solar()[0],month,day)#下标和位置
            date_str = solar_date.strftime('%Y%m%d')
            try:
                list = anniversaries[date_str]
            except Exception as e:
                anniversaries[date_str] = []
                list = anniversaries[date_str]
            list.append({'anniversary':anniversary_handle(value),'solar':False})

        for key,value in SOLAR_ANNIVERSARY.items():
            date_str = str(self._lunar.solar()[0])+key #20200101
            try:
                list = anniversaries[date_str]
            except Exception as e:
                anniversaries[date_str] = []
                list = anniversaries[date_str]
            list.append({'anniversary':anniversary_handle(value),'solar':True})


    #根据key 排序 因为key就是日期字符串
        list=sorted(anniversaries.items(),key=lambda x:x[0])
        #找到第一个大于今天的纪念日
        for item in list:
            key = item[0]
            annis = item[1] #纪念日数组
            now_str = datetime.datetime.now().strftime('%Y-%m-%d')
            today = datetime.datetime.strptime(now_str, "%Y-%m-%d")
            last_update = datetime.datetime.strptime(key,'%Y%m%d')
            days = (last_update - today).days
            if days > 0:
                return key,days,annis
        return None,None,None

    #今天是否是自定义的纪念日（阴历和阳历）
    def custom_anniversary(self):
        l_month = self._lunar.lunar()[1]
        l_day = self._lunar.lunar()[2]
        s_month = self._lunar.solar()[1]
        s_day = self._lunar.solar()[2]
        l_anni = lunar.festival_handle(LUNAR_ANNIVERSARY,l_month,l_day)
        s_anni = lunar.festival_handle(SOLAR_ANNIVERSARY,s_month,s_day)
        anni = ''
        if l_anni:
            anni += l_anni
        if s_anni:
            anni += s_anni
        return anni


    def calculate_age(self):
        if not CALCULATE_AGE:
            return
        now_day = datetime.datetime.now()
        count_dict = {}
        for item in CALCULATE_AGE:
            date = item[CONF_CALCULATE_AGE_DATE]
            name = item[CONF_CALCULATE_AGE_NAME]
            key = datetime.datetime.strptime(date,'%Y-%m-%d %H:%M:%S')
            if (now_day - key).total_seconds() > 0:
                total_seconds = int((now_day - key).total_seconds())
                year, remainder = divmod(total_seconds,60*60*24*365)
                day, remainder = divmod(remainder,60*60*24)
                hour, remainder = divmod(remainder,60*60)
                minute, second = divmod(remainder,60)
                self.attributes['离'+name+'过去'] = '{}年 {} 天 {} 小时 {} 分钟 {} 秒'.format(year,day,hour,minute,second)
            if (now_day - key).total_seconds() < 0:
                total_seconds = int((key - now_day ).total_seconds())
                year, remainder = divmod(total_seconds,60*60*24*365)
                day, remainder = divmod(remainder,60*60*24)
                hour, remainder = divmod(remainder,60*60)
                minute, second = divmod(remainder,60)
                self.attributes['离'+name+'还差']  = '{}年 {} 天 {} 小时 {} 分钟 {} 秒'.format(year,day,hour,minute,second)


    def nearest_holiday(self):
        '''查找离今天最近的法定节假日，并显示天数'''
        now_day = datetime.date.today()
        count_dict = {}
        results = self._holiday.getHoliday()
        for key in results.keys():
            if (key - now_day).days > 0:
                count_dict[key] = (key - now_day).days
        nearest_holiday_dict = {}
        if count_dict:
            nearest_holiday_dict['name'] = results[min(count_dict)]
            nearest_holiday_dict['date'] = min(count_dict).isoformat()
            nearest_holiday_dict['day'] = str((min(count_dict)-now_day).days)+'天'

        return nearest_holiday_dict

    def _update(self):
        self.attributes = {} #重置attributes
        self._lunar = lunar.CalendarToday()#重新赋值

        self._state = self._holiday.is_holiday_today()
        self.attributes['今天'] = self._lunar.solar_date_description()
        # self.attributes['今天'] = datetime.date.today().strftime('%Y{y}%m{m}%d{d}').format(y='年', m='月', d='日')
        self.attributes['星期'] = self._lunar.week_description()
        self.attributes['农历'] = self._lunar.lunar_date_description()
        term = self._lunar.solar_Term()
        if term:
            self.attributes['节气'] = term
        festival = self._lunar.festival_description()
        if festival:
            self.attributes['节日'] = festival

        custom = self.custom_anniversary()
        if custom:
            self.attributes['纪念日'] = custom

        key,days,annis = self.calculate_anniversary()
        s = ''
        if key and days and annis:
            for anni in annis:
                s += anni['anniversary']

            self.attributes['离最近的纪念日'] = s + '还有' + str(days) + '天'

        nearest = self.nearest_holiday()
        if nearest:
            self.attributes['离今天最近的法定节日'] = nearest['name']
            self.attributes['法定节日日期'] = nearest['date']
            self.attributes['还有'] = nearest['day']

        self.calculate_age()
