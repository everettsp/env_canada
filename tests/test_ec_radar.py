import asyncio
from datetime import datetime
from io import BytesIO
from PIL import Image

import pytest

from env_canada import ec_radar, ECRadar


def test_get_station_coords():
    coords = ec_radar.get_station_coords("XFT")
    assert coords == (45.04101, -76.11617)


def test_get_bounding_box():
    box_corners = ec_radar.compute_bounding_box(200, 45.04101, -76.11617)
    assert box_corners == (43.24237, -78.66207, 46.83965, -73.57027)


@pytest.mark.parametrize(
    "init_parameters",
    [
        {"station_id": "xft", "precip_type": "rain"},
        {"coordinates": (50, -100), "precip_type": "snow"},
    ],
)
def test_ecradar(init_parameters):
    radar = ECRadar(**init_parameters)
    assert isinstance(radar, ECRadar)


@pytest.fixture
def test_radar():
    return ECRadar(station_id="XFT")


def test_get_dimensions(test_radar):
    dimensions = asyncio.run(test_radar._get_dimensions())
    assert isinstance(dimensions[0], datetime) and isinstance(dimensions[1], datetime)


def test_get_latest_frame(test_radar):
    frame = asyncio.run(test_radar.get_latest_frame())
    image = Image.open(BytesIO(frame))
    assert image.format == "PNG"


def test_get_loop(test_radar):
    loop = asyncio.run(test_radar.get_loop())
    image = Image.open(BytesIO(loop))
    assert image.format == "GIF" and image.is_animated
