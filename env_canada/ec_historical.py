import copy
import csv
from io import StringIO
import logging
import xml.etree.ElementTree as et

from aiohttp import ClientSession
from dateutil import parser, tz
import lxml.html


STATIONS_URL = "https://climate.weather.gc.ca/historical_data/search_historic_data_stations_{}.html"

WEATHER_URL = "https://climate.weather.gc.ca/climate_data/bulk_data_{}.html"

LOG = logging.getLogger(__name__)

stationdata_meta = {
    "maxtemp": {
        "xpath": "./maxtemp",
        "type": "float",
        "units": "°C",
        "english": "Maximum Temperature",
        "french": "Température maximale",
    },
    "mintemp": {
        "xpath": "./mintemp",
        "type": "float",
        "units": "°C",
        "english": "Minimum Temperature",
        "french": "Température minimale",
    },
    "meantemp": {
        "xpath": "./meantemp",
        "type": "float",
        "units": "°C",
        "english": "Mean Temperature",
        "french": "Température moyenne",
    },
    "heatdegdays": {
        "xpath": "./heatdegdays",
        "type": "float",
        "units": "°C",
        "english": "Heating Degree Days",
        "french": "Degré-jour de chauffage",
    },
    "cooldegdays": {
        "xpath": "./cooldegdays",
        "type": "float",
        "units": "°C",
        "english": "Cooling Degree Days",
        "french": "Degré-jour de réfrigération",
    },
    "totalrain": {
        "xpath": "./totalrain",
        "type": "float",
        "units": "mm",
        "english": "Total Rain",
        "french": "Pluie totale",
    },
    "totalsnow": {
        "xpath": "./totalsnow",
        "type": "float",
        "units": "cm",
        "english": "Total Snow",
        "french": "Neige totale",
    },
    "totalprecipitation": {
        "xpath": "./totalprecipitation",
        "type": "float",
        "units": "mm",
        "english": "Total Precipitation",
        "french": "Précipitations totales",
    },
    "snowonground": {
        "xpath": "./snowonground",
        "type": "float",
        "units": "cm",
        "english": "Snow on Ground",
        "french": "Neige au sol",
    },
    "dirofmaxgust": {
        "xpath": "./dirofmaxgust",
        "type": "int",
        "units": "10s Deg",
        "english": "Direction of Maximum Gust",
        "french": "Direction de la rafale maximale",
    },
    "speedofmaxgust": {
        "xpath": "./speedofmaxgust",
        "type": "int",
        "units": "km/h",
        "english": "Speed of Maximum Gust",
        "french": "Vitesse de la rafale maximale",
    },
}

metadata_meta = {
    "name": {"xpath": "./stationinformation/name"},
    "province": {"xpath": "./stationinformation/province"},
    "stationoperator": {"xpath": "./stationinformation/stationoperator"},
    "latitude": {"xpath": "./stationinformation/latitude"},
    "longitude": {"xpath": "./stationinformation/longitude"},
    "elevation": {"xpath": "./stationinformation/elevation"},
    "climate_identifier": {"xpath": "./stationinformation/climate_identifier"},
    "wmo_identifier": {"xpath": "./stationinformation/wmo_identifier"},
    "tc_identifier": {"xpath": "./stationinformation/tc_identifier"},
}


def parse_timestamp(t):
    return parser.parse(t).replace(tzinfo=tz.UTC)


async def get_historical_stations(
    coordinates, radius=25, start_year=1840, end_year=2021, limit=25, language="english"
):
    """Get list of all historical stations from Environment Canada"""
    lat, lng = coordinates
    params = {
        "searchType": "stnProx",
        "timeframe": 2,
        "txtRadius": radius,
        "optProxType": "decimal",
        "txtLatDecDeg": lat,
        "txtLongDecDeg": lng,
        "optLimit": "yearRange",
        "StartYear": start_year,
        "EndYear": end_year,
        "Year": start_year,
        "Month": "1",
        "Day": "1",
        "selRowPerPage": limit,
        "selCity": "",
        "selPark": "",
        "txtCentralLatDeg": "",
        "txtCentralLatMin": "",
        "txtCentralLatSec": "",
        "txtCentralLongDeg": "",
        "txtCentralLongMin": "",
        "txtCentralLongSec": "",
    }

    async with ClientSession() as session:
        response = await session.get(
            STATIONS_URL.format(language[0]), params=params, timeout=10
        )
        result = await response.read()

        station_html = result.decode("utf-8")
        station_tree = lxml.html.fromstring(station_html)
        station_req_forms = station_tree.xpath(
            "//form[starts-with(@id, 'stnRequest') and '-sm' = substring(@id, string-length(@id) - string-length('-sm') +1)]"
        )

        stations = {}
        for station_req_form in station_req_forms:
            station = {}
            station_name = station_req_form.xpath(
                './/div[@class="col-md-10 col-sm-8 col-xs-8"]'
            )[0].text
            station["prov"] = station_req_form.xpath(
                './/div[@class="col-md-10 col-sm-8 col-xs-8"]'
            )[1].text
            station["proximity"] = float(
                station_req_form.xpath('.//div[@class="col-md-10 col-sm-8 col-xs-8"]')[
                    2
                ].text
            )
            station["id"] = station_req_form.find(
                "input[@name='StationID']"
            ).attrib.get("value")
            station["hlyRange"] = station_req_form.find(
                "input[@name='hlyRange']"
            ).attrib.get("value")
            station["dlyRange"] = station_req_form.find(
                "input[@name='dlyRange']"
            ).attrib.get("value")
            station["mlyRange"] = station_req_form.find(
                "input[@name='mlyRange']"
            ).attrib.get("value")
            stations[station_name] = station

        return stations


class ECHistorical(object):

    """Get historical weather data from Environment Canada."""

    def __init__(self, station_id, year, language="english", format="xml"):
        """Initialize the data object."""
        self.station_id = station_id
        self.year = year
        self.language = language
        self.format = format
        self.timeframe = 2
        self.submit = "Download+Data"

        self.metadata = {}
        self.station_data = {}

    async def update(self):
        """Get the historical data from Environment Canada."""

        params = {
            "stationID": self.station_id,
            "Year": self.year,
            "format": self.format,
            "timeframe": self.timeframe,
            "submit": self.submit,
        }

        # Get historical weather data

        async with ClientSession() as session:
            response = await session.get(
                WEATHER_URL.format(self.language[0]), params=params, timeout=10
            )
            if self.format == "csv":
                result = await response.text()

                f = StringIO(result)

                self.station_data = copy.deepcopy(f)

                reader = csv.reader(f, delimiter=",")

                # headers
                next(reader)

                # first row of data
                firstrow = next(reader)

                self.metadata = {
                    "longitude": firstrow[0],
                    "latitude": firstrow[1],
                    "name": firstrow[2],
                    "climate_identifier": firstrow[3],
                }

            else:
                result = await response.read()

                weather_xml = result.decode("utf-8")
                weather_tree = et.fromstring(weather_xml)

                # Update metadata
                for m, meta in metadata_meta.items():
                    element = weather_tree.find(meta["xpath"])
                    if element is not None:
                        self.metadata[m] = weather_tree.find(meta["xpath"]).text
                    else:
                        self.metadata[m] = None

                # Update station data
                def get_stationdata(meta, stationdata_element, language):
                    stationdata = {}

                    element = stationdata_element.find(meta["xpath"])

                    if element is None or element.text is None:
                        stationdata["value"] = None
                    else:
                        if meta.get("attribute"):
                            stationdata["value"] = element.attrib.get(meta["attribute"])
                        else:
                            if meta["type"] == "int":
                                stationdata["value"] = int(element.text)
                            elif meta["type"] == "float":
                                stationdata["value"] = float(
                                    element.text.replace(",", ".")
                                )
                            else:
                                stationdata["value"] = element.text

                            if element.attrib.get("units"):
                                stationdata["unit"] = element.attrib.get("units")
                    stationdata["label"] = meta[language]
                    return stationdata

                stationdata_elements = weather_tree.findall("./stationdata")

                for stationdata_element in stationdata_elements:
                    day = stationdata_element.attrib.get("day")
                    month = stationdata_element.attrib.get("month")
                    year = stationdata_element.attrib.get("year")
                    dt = parse_timestamp(f"{year}-{month}-{day}").date()

                    cur_station_data = {}

                    for s, meta in stationdata_meta.items():
                        cur_station_data[s] = get_stationdata(
                            meta, stationdata_element, self.language
                        )

                    self.station_data[str(dt)] = cur_station_data