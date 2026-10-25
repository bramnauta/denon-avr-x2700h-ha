"""Constants for the Denon AVR-X2700H integration."""

from __future__ import annotations

DOMAIN = "denon_avr_x2700h"
MANUFACTURER = "Denon"
DEFAULT_NAME = "Denon AVR-X2700H"

CONF_ZONE2 = "zone2"
CONF_MAX_VOLUME = "max_volume"
CONF_VOLUME_STEP = "volume_step"

DEFAULT_ZONE2 = True
DEFAULT_MAX_VOLUME = 0.0  # dB; maps to volume_level 1.0
DEFAULT_VOLUME_STEP = 0.5  # dB

SERVICE_SEND_COMMAND = "send_command"
SERVICE_SAVE_QUICK_SELECT = "save_quick_select"
SERVICE_SET_TUNER_FREQUENCY = "set_tuner_frequency"
SERVICE_REFRESH = "refresh"

ATTR_COMMAND = "command"
ATTR_WAIT = "wait"
ATTR_SLOT = "slot"
ATTR_FREQUENCY = "frequency"
