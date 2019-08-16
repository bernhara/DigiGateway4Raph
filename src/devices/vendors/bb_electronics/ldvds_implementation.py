############################################################################
#                                                                          #
# Copyright (c)2010, Digi International (Digi). All Rights Reserved.       #
#                                                                          #
# Permission to use, copy, modify, and distribute this software and its    #
# documentation, without fee and without a signed licensing agreement, is  #
# hereby granted, provided that the software is used on Digi products only #
# and that the software contain this copyright notice,  and the following  #
# two paragraphs appear in all copies, modifications, and distributions as #
# well. Contact Product Management, Digi International, Inc., 11001 Bren   #
# Road East, Minnetonka, MN, +1 952-912-3444, for commercial licensing     #
# opportunities for non-Digi products.                                     #
#                                                                          #
# DIGI SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING, BUT NOT LIMITED   #
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A          #
# PARTICULAR PURPOSE. THE SOFTWARE AND ACCOMPANYING DOCUMENTATION, IF ANY, #
# PROVIDED HEREUNDER IS PROVIDED "AS IS" AND WITHOUT WARRANTY OF ANY KIND. #
# DIGI HAS NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT, UPDATES,         #
# ENHANCEMENTS, OR MODIFICATIONS.                                          #
#                                                                          #
# IN NO EVENT SHALL DIGI BE LIABLE TO ANY PARTY FOR DIRECT, INDIRECT,      #
# SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOST PROFITS,   #
# ARISING OUT OF THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION, EVEN IF   #
# DIGI HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.                #
#                                                                          #
############################################################################

"""\
Implementation of the AutoTap LDVDS protocol.
"""

import threading, time, math
from socket import *

from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
    import XBeeConfigBlockDDO
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.addressing import *

# class LowLevelCommunicator:
#     """Wraps Communication for Python"""

#     def __init__(self, addr, callback):
#	  self.callback = callback
#	  self.sd = socket(AF_ZIGBEE, SOCK_DGRAM, XBS_PROT_TRANSPORT)
#	  self.sd.bind(("", 0xe8, 0, 0))
#	  self.DESTINATION=(addr, 0xe8, 0xc105, 0x11)
#	  threading.Thread(target=self._dataReceived).start()
#     #from core.tracing import get_tracer
#     #_tracer = get_tracer("ldvds_implementation.LowLevelCommunicator")

#     def writeBytes(self, data):
#	  for val in data:
#	      sd.sendto(chr(val), 0, self.DESTINATION)

#     def writeFrame(self, data):
#	  checksum = 0
#	  frameWritten = ""
#	  asciiToSend = ""
#	  for val in data:
#	      frameWritten += "%02X " % val
#	      checksum += val
#	      asciiToSend += chr(val) #self.ser.write(chr(val))
#	  checksum = checksum & 0xFF
#	  frameWritten += "%02X " % checksum
#	  asciiToSend += chr(checksum) #self.ser.write(chr(checksum))
#	  self.sd.sendto(asciiToSend, 0, self.DESTINATION)
#	  #_tracer.info("Sent Full Frame: " + frameWritten)

#     def _dataReceived(self):
#	  receivedData = []
#	  i = 0
#	  try:
#	      while True:
#		  data, src_addr = self.sd.recvfrom(72)
#		  for val in data:
#		      self.callback(ord(val))
#	  except Exception, e:
#	      self.__tracer.error(e)

#     def close(self):
#	  self.sd.close()

class LowLevelCommunicator:
     """Wraps Communication for Python"""

     def __init__(self, xbee_manager, addr, callback):
	  self.__xbee_manager = xbee_manager
	  self.__addr = addr
	  self.__callback = callback
	  self.DESTINATION=(addr, 0xe8, 0xc105, 0x11)

	  self.__xbee_manager.xbee_device_register(self)

	  # Create a callback specification for our device address, endpoint
	  # Digi XBee profile and sample cluster id:
	  xbdm_rx_event_spec = XBeeDeviceManagerRxEventSpec()
	  xbdm_rx_event_spec.cb_set(self._dataReceived)
	  xbdm_rx_event_spec.match_spec_set(
	       (addr, 0xe8, 0xc105, 0x11),
	       (True, True, True, True))
	  self.__xbee_manager.xbee_device_event_spec_add(self,
							 xbdm_rx_event_spec)

	  # Create a DDO configuration block for this device:
	  xbee_ddo_cfg = XBeeConfigBlockDDO(addr)

	  # Get the gateway's extended address:
	  gw_xbee_sh, gw_xbee_sl = gw_extended_address_tuple()

	  # Set the destination for data to be the gateway:
	  xbee_ddo_cfg.add_parameter('DH', gw_xbee_sh)
	  xbee_ddo_cfg.add_parameter('DL', gw_xbee_sl)

	  # TODO, might want to think about adding serial config, etc.

	  # Register this configuration block with the XBee Device Manager:
	  self.__xbee_manager.xbee_device_config_block_add(self, xbee_ddo_cfg)

	  # Indicate that we have no more configuration to add:
	  self.__xbee_manager.xbee_device_configure(self)

     def writeBytes(self, data):
	  xmit_data = [chr(c) for c in data]
	  for val in data:
	       self.__xbee_manager.xbee_device_xmit(self, 0xe8, xmit_data,
						    self.DESTINATION)

     def writeFrame(self, data):
	  checksum = 0
	  asciiToSend = ""
	  for val in data:
	       checksum += val
	       asciiToSend += chr(val)
	  checksum = checksum & 0xFF
	  asciiToSend += chr(checksum)
	  self.__xbee_manager.xbee_device_xmit(0xe8, asciiToSend,
					       self.DESTINATION)

     def _dataReceived(self, buf, addr):
	  for val in buf:
	       self.__callback(ord(val))

     def close(self):
	  self.__xbee_manager.xbee_device_unregister(self)

class FrameManager:
    """Handles low level communication with the AutoTap OBDII Streamer"""
    SERIAL_BAUD_RESPONSE = 0x95		   #
    SUPPORTED_PARAMETERS_RESPONSE = 0xA0   #
    GET_PARAMETER_RESPONSE = 0xA2	   # [0xA2, p1, p2, ...] -> [None] || [paramVal, paramVal2, ...]
    REDETECT_RESPONSE = 0xA4		   #
    GET_VIN_RESPONSE = [0xA5, 0x00]	   #
    DTC_RESPONSE =  [0xA5, 0x02]	   #
    SETUP_TIME_UPDATE_RESPONSE = 0xB0	   #
    SETUP_UPDATE_MODE_RESPONSE = 0xB5	   #

    VEHICLE_INFO_UPDATE = 0xA5
    VEHICLE_INFO_VIN_OPTION = 0x00
    VEHICLE_INFO_DTC_OPTION = 0x02
    DEVICE_CONFIGURED_MESSAGE = 0x80
    VEHICLE_NOT_DETECTED_MESSAGE = 0x81

    TIME_BASED_PARAMETER_UPDATE = 0xC0 #Same format as 0x22 response

    PID_BYTE_LENGTH_MAP = {0x00:2,  0x01:2,  0x02:2,  0x03:4,  0x04:2,	0x05:2,
			   0x06:2,  0x08:2,  0x09:2,  0x0A:2,  0x0B:2,	0x0C:2,
			   0x0D:2,  0x0E:2,  0x0F:2,  0x10:2,  0x11:2,	0x12:2,
			   0x13:2,  0x14:2,  0x15:2,  0x16:2,  0x17:2,	0x18:2,
			   0x19:2,  0x1A:2,  0x1B:2,  0x1D:2,  0x1E:2,	0x1F:2,
			   0x20:2,  0x21:2,  0x22:4,  0x23:4}

    PID_CONVERSION_MAP = {0x00:410,  0x01:4,  0x02:655,	 0x03:1,  0x04:655,
			  0x05:131,  0x06:1,  0x08:1,  0x09:1,	0x0A:1,
			  0x0B:1,  0x0C:2185,  0x0D:3641,  0x0E:1,  0x0F:1,
			  0x10:1,  0x11:1,  0x12:1,  0x13:1,  0x14:1,
			  0x15:1,  0x16:1,  0x17:1,  0x18:1,  0x19:1,
			  0x1A:1,  0x1B:1,  0x1D:1,  0x1E:1,  0x1F:1,
			  0x20:1,  0x21:1,  0x22:10,  0x23:128}

    def __init__(self, handleTimeBasedParameterCallback, xbee_manager,
							 addr_extended):
	self.deviceIsReady = False
	self.pendingCommands = {}
	self.timeout = 5
	self.receivedData = []
	self.handleTimeBasedParameterCallback = handleTimeBasedParameterCallback
	self.lowLevelCommunicator = LowLevelCommunicator(xbee_manager,
							 addr_extended,
							 self.handleReceivedData)
							 
	# from core.tracing import get_tracer
	# self.__tracer = get_tracer("ldvds_implementation.FrameManager")

    def close(self):
	self.lowLevelCommunicator.close()

    def handleReceivedData(self, data):
	#self.__tracer.info("Received Byte: %02X ", data)

	if len(self.receivedData) == 0: # Empty Frame
	    if data == 0x01: # New frame delimiter encountered
		self.receivedData.append(data)
		self.controlLength = -1
		self.dataLength = -1
	elif self.controlLength == -1: # Picked up control length byte
	    self.receivedData.append(data)
	    self.controlLength = data
	elif self.controlLength > 0:
	    self.receivedData.append(data)
	    self.controlLength -= 1
	elif self.dataLength == -1: # Picked up data length byte
	    self.receivedData.append(data)
	    self.dataLength = data
	elif self.dataLength > 0:
	    self.receivedData.append(data)
	    self.dataLength -= 1
	else: # Only other possibility should be encountering checksum
	    calculatedChecksum = 0
	    for value in self.receivedData:
		calculatedChecksum += value
	    calculatedChecksum = calculatedChecksum & 0xFF

	    if calculatedChecksum != data:
		#self.__tracer.warning("Bad checksum!")
		pass
	    else:
		self.receivedData.append(data)
		self.handleFullFrame(self.receivedData)

	    self.receivedData = []

    def handleFullFrame(self, frame):
	toprint = ""
	for val in frame:
	    toprint += "%02X " % val
	#self.__tracer.info("Received Full Frame: " + toprint)

	#time.sleep(.5)

	startDelimeter = frame.pop(0)
	commandDataLength = frame.pop(0)
	command = frame.pop(0)
	dataLength = frame.pop(0)
	checksum = frame.pop()

	#At this point, we have stripped off the
	#frame information and are only left with the
	#command data

	if command == FrameManager.GET_PARAMETER_RESPONSE:
	    #self.__tracer.info("Received GET_PARAMETER_RESPONSE")
	    #self.__tracer.info(frame)
	    parameters = []
	    paramValues = []
	    while len(frame) > 0:
		pid = frame.pop(0)
		parameters.append(pid)
		paramLength = FrameManager.PID_BYTE_LENGTH_MAP[pid]
		for paramData in range(0, paramLength):
		    paramValues.append(frame.pop(0))

	    parameters.insert(0, command)

	    key = tuple(parameters)

	    if self.pendingCommands.has_key(key):
		self.pendingCommands[key] = paramValues

	elif command == FrameManager.REDETECT_RESPONSE:
	    #self.__tracer.info("Received FORCE_REDETECT_RESPONSE")
	    key = [FrameManager.REDETECT_RESPONSE]
	    key = tuple(key)
	    if self.pendingCommands.has_key(key):
		self.pendingCommands[key] = True

	elif command == FrameManager.VEHICLE_INFO_UPDATE:
	    #self.__tracer.info("Received VEHICLE_INFO_UPDATE")
	    info_type = frame.pop(0)
	    if info_type == FrameManager.VEHICLE_INFO_VIN_OPTION:
		#self.__tracer.info("\tVIN Info")
		key = tuple(FrameManager.GET_VIN_RESPONSE)
		if self.pendingCommands.has_key(key):
		    self.pendingCommands[key] = frame
	    elif info_type == FrameManager.VEHICLE_INFO_DTC_OPTION:
		#self.__tracer.info("\tDTC Info")
		key = tuple(FrameManager.DTC_RESPONSE)
		if self.pendingCommands.has_key(key):
		    self.pendingCommands[key] = frame

	elif command == FrameManager.SUPPORTED_PARAMETERS_RESPONSE:
	    #self.__tracer.info("Received SUPPORTED_PARAMETERS_RESPONSE")
	    #self.__tracer.info(frame)
	    key = [FrameManager.SUPPORTED_PARAMETERS_RESPONSE]
	    key = tuple(key)
	    if self.pendingCommands.has_key(key):
		self.pendingCommands[key] = frame

	elif command == FrameManager.SETUP_UPDATE_MODE_RESPONSE:
	    #self.__tracer.info("Received SETUP_UPDATE_MODE_RESPONSE")
	    key = [FrameManager.SETUP_UPDATE_MODE_RESPONSE]
	    key = tuple(key)
	    if self.pendingCommands.has_key(key):
		self.pendingCommands[key] = True

	elif command == FrameManager.SETUP_TIME_UPDATE_RESPONSE:
	    #self.__tracer.info("Received SETUP_TIME_UPDATE_RESPONSE")
	    key = [FrameManager.SETUP_TIME_UPDATE_RESPONSE, frame.pop(0)]
	    key = tuple(key)
	    if self.pendingCommands.has_key(key):
		self.pendingCommands[key] = True
	elif command == FrameManager.TIME_BASED_PARAMETER_UPDATE:
	    #self.__tracer.info("Received TIME_BASED_PARAMETER_UPDATE")

	    paramValueMap = {}

	    while len(frame) > 0:
		pid = frame.pop(0)
		paramLength = FrameManager.PID_BYTE_LENGTH_MAP[pid]
		value = 0
		for paramData in range(0, paramLength):
		    value <<= 8
		    value += frame.pop(0)

		value /= float(FrameManager.PID_CONVERSION_MAP[pid])
		paramValueMap[pid] = value

	    self.handleTimeBasedParameterCallback(paramValueMap)
	elif command == FrameManager.DEVICE_CONFIGURED_MESSAGE:
	    #self.__tracer.info("Received DEVICE_CONFIGURED_MESSAGE")
	    self.deviceIsReady = True
	elif command == FrameManager.VEHICLE_NOT_DETECTED_MESSAGE:
	    #self.__tracer.info("Received VEHICLE_NOT_DETECTED_MESSAGE")
	    self.deviceIsReady = False


    def getParameters(self, parameters):
	pendingKey = [FrameManager.GET_PARAMETER_RESPONSE]
	getParamMessage = [0x01, 0x01, 0x22]  # Start Delimiter, Control Length, Control Data
	getParamMessage.append(len(parameters))
	for pid in parameters:
	    pendingKey.append(pid)
	    getParamMessage.append(pid)

	pendingKey = tuple(pendingKey)

	response = self.__waitForResponse(getParamMessage, pendingKey)

	if response == None:
	    return None

	convertedParameterValues = []

	for pid in parameters:
	    val = 0
	    for pos in range(0, FrameManager.PID_BYTE_LENGTH_MAP[pid]):
		val <<= 8
		val += response.pop(0)
	    val /= float(FrameManager.PID_CONVERSION_MAP[pid])
	    convertedParameterValues.append(val)

	return convertedParameterValues

    def forceRedetect(self):
	pendingKey = [FrameManager.REDETECT_RESPONSE]
	redetectMessage = [0x01, 0x01, 0x24, 0x00]

	pendingKey = tuple(pendingKey)

	response = self.__waitForResponse(redetectMessage, pendingKey)

	if response == None:
	    return None
	else:
	    return True

    def getDTCs(self):
	pendingKey = tuple(FrameManager.DTC_RESPONSE)
	reqestDTCMessage = [0x01, 0x01, 0x25, 0x01, 0x02]

	response = self.__waitForResponse(reqestDTCMessage, pendingKey)

	if response == None:
	    return None
	else:
	    troubleCodes = []
	    currentCode = ""
	    while len(response) > 0:
		currentCode += chr(response.pop(0))
		if len(currentCode) == 5:
		    troubleCodes.append(currentCode)
		    currentCode = ""

	    return troubleCodes

    def getVIN(self):
	pendingKey = tuple(FrameManager.GET_VIN_RESPONSE)
	requestDTCMessage = [0x01, 0x01, 0x25, 0x01, 0x00]

	response = self.__waitForResponse(requestDTCMessage, pendingKey)

	if response == None:
	    return None
	else:
	    vin = ""
	    for val in response:
		vin += chr(val)

	    return vin

    def getSupportedParameters(self):
	pendingKey = [FrameManager.SUPPORTED_PARAMETERS_RESPONSE]
	requestSupportedParametersMessage = [0x01, 0x01, 0x20, 0x00]

	pendingKey = tuple(pendingKey)

	response = self.__waitForResponse(requestSupportedParametersMessage, pendingKey)

	if response == None:
	    self.deviceIsReady = False
	else:
	    self.deviceIsReady = True

	return response

    def enableTimeBasedMode(self, enabled):
	pendingKey = [FrameManager.SETUP_UPDATE_MODE_RESPONSE]
	setupTimeModeMessage = [0x01, 0x01, 0x35, 0x02, 0x00, enabled]

	pendingKey = tuple(pendingKey)

	response = self.__waitForResponse(setupTimeModeMessage, pendingKey)

	return response

    def enableTimeBasedRetrieval(self, parameter, enabled, interval):
	pendingKey = [FrameManager.SETUP_TIME_UPDATE_RESPONSE, parameter]
	intervalLowByte = interval & 0xFF
	intervalHighByte = interval >> 8
	setupTimeRetrievalMessage = [0x01, 0x01, 0x30, 0x04, parameter, enabled,  intervalHighByte, intervalLowByte]

	pendingKey = tuple(pendingKey)

	response = self.__waitForResponse(setupTimeRetrievalMessage, pendingKey)

	return response

    def getDeviceIsReady(self):
	self.getSupportedParameters()

	return self.deviceIsReady

    def __waitForResponse(self, message, pendingKey):
	"""Takes information about a sent message and watches for the response,
	eventually timing out if it is not received.

	"""
	self.pendingCommands[pendingKey] = None

	self.lowLevelCommunicator.writeFrame(message)

	elapsedTime = 0
	while(elapsedTime < self.timeout and self.pendingCommands.has_key(pendingKey) and self.pendingCommands[pendingKey] == None):
	    time.sleep(0.1)
	    elapsedTime += 0.1

	if not self.pendingCommands.has_key(pendingKey):
	    returnVal = None
	else:
	    returnVal = self.pendingCommands[pendingKey]
	    del self.pendingCommands[pendingKey]

	return returnVal

class AutoTapStreamer:
    """Provides high level access to the LVDVD-S AutoTap Streamer.

    It provides simplified methods for ensuring that the device is capable
    of communicating with the vehicle, and then retrieving the desired
    information once communication has been established.

    """

    PID_NAME_MAP = {0x00:"Vehicle Speed", 0x01:"Engine Speed",
		  0x02:"Throttle Position", 0x03:"Odometer",
		  0x04:"Fuel Level", 0x05:"Fuel Level Remaining",
		  0x06:"Transmission Gear", 0x08:"Ignition Status",
		  0x09:"MIL Status", 0x0A:"Airbag Dash Indicator",
		  0x0B:"ABS Dash Indicator", 0x0C:"Fuel Rate",
		  0x0D:"Battery Voltage", 0x0E:"PTO Status",
		  0x0F:"Seatbelt Fastened", 0x10:"Misfire Monitor",
		  0x11:"Fuel System Monitor", 0x12:"Comprehensive Component Monitor",
		  0x13:"Catalyst Monitor", 0x14:"Heated Catalyst Monitor",
		  0x15:"Evaporative System Monitor", 0x16:"Secondary Air System Monitor",
		  0x17:"A/C System Refrigerant Monitor", 0x18:"Oxygen Sensor Monitor",
		  0x19:"Oxygen Sensor Heater Monitor", 0x1A:"EGR System Monitor",
		  0x1B:"Brake Switch Status", 0x1D:"Cruise Control Status",
		  0x1E:"Turn Signal Status", 0x1F:"Oil Pressure Lamp",
		  0x20:"Brake Indicator Light", 0x21:"Coolant Hot Lamp",
		  0x22:"Trip Odometer", 0x23:"Trip Fuel Consumption"}

    PID_UNIT_MAP = {0x00:"MPH", 0x01:"RPM",
		  0x02:"%", 0x03:"Miles",
		  0x04:"%", 0x05:"Gallons",
		  0x06:"", 0x08:"",
		  0x09:"", 0x0A:"",
		  0x0B:"", 0x0C:"Gallons per Hour",
		  0x0D:"Volts", 0x0E:"",
		  0x0F:"", 0x10:"",
		  0x11:"", 0x12:"",
		  0x13:"", 0x14:"",
		  0x15:"", 0x16:"",
		  0x17:"", 0x18:"",
		  0x19:"", 0x1A:"",
		  0x1B:"", 0x1D:"",
		  0x1E:"", 0x1F:"",
		  0x20:"", 0x21:"",
		  0x22:"Miles", 0x23:"Gallons"}

    def __init__(self, xbee_manager, addr_extended):
	"""Create an instance of the AutoTapStreamer for communication"""
	self.parameterCallbacks = set()
	self.frameManager = FrameManager(self.handleTimeBasedParameterUpdate,
					 xbee_manager, addr_extended)

    def close(self):
	self.frameManager.close()

    def forceRedetect(self):
	"""Force the AutoTap Streamer to retrieve vehicle information.

	The AutoTap Streamer saves information about the vehicle it is connected to
	in order to reduce the time it takes to go from power up to being ready for
	communication.	This command needs to be called when moving the AutoTap Streamer
	to a new vehicle, so it will retrieve the necessary information from the vehicle

	Returns True on a successful send, False otherwise.
	"""

	returnVal = self.frameManager.forceRedetect()

	if returnVal:
	    return True
	else:
	    return False

    def readyForCommunication(self):
	"""Return communication state of the AutoTap Streamer.

	It may take up to a minute for the AutoTap Streamer to perform
	startup procedures and be ready to communicate with the vehicle.

	This method returns True if the device is ready for communication
	with the vehicle, False if it is still pending, or None if we were
	unable to detect the state of the device.
	"""

	return self.frameManager.getDeviceIsReady()

    def getVIN(self):
	"""Return VIN of the vehicle.

	Returns the VIN of the vehicle, else False on a failure to read
	"""

	returnValue = self.frameManager.getVIN()
	if returnValue == None:
	    return False
	else:
	    return returnValue

    def getDiagnosticTroubleCodes(self):
	"""Return list of diagnostic trouble codes.

	Returns a list of 5 character diagnostic codes, or False on
	failure to retrieve.
	"""

	returnValue = self.frameManager.getDTCs()
	if returnValue == None:
	    return False
	else:
	    return returnValue

    def getSupportedParameters(self):
	"""Return list of supported parameters for the vehicle

	Returns a list of Parameter IDs that are supported by this vehicle, or False if we
	were unable to retrieve them.
	"""

	returnValue = self.frameManager.getSupportedParameters()
	if returnValue == None:
	    return False
	else:
	    return returnValue

    def getParameterValues(self, parameters):
	"""Retrieve current vehicle parameters

	Return a diction mapping the requested parameters to their current value, or False
	on a failure during retrieval.	Up to 11 parameters can be requested per month.
	"""

	values = self.frameManager.getParameters(parameters)

	if(values == None):
	    return False

	returnData = {}

	for (pid,val) in map(None, parameters, values):
	    returnData[pid] = val

	return returnData

    def enableTimeBasedRetrieval(self, parameter, enable, interval):
	"""Configure automatic reporting of given parameter.

	For the given parameter, enable=True will turn on automatic
	updates for the parameter, where enable=False will disable this functionality.

	interval is given as a multiple of 50 ms, ranging from 1 (50 ms update) to 65535
	for an interval of 54.6 minutes.

	Parameter updates will be returned asynchrously through the callback specified
	in the addParameterCallback function.

	Returns True on successful configuration, False otherwise.

	"""

	returnValue = self.frameManager.enableTimeBasedRetrieval(parameter, enable, interval)

	if returnValue == None:
	    return False
	else:
	    return True

    def enableTimeBasedMode(self, enable):
	"""Configure automatic parameter update mode

	This method turns on or off the entire time based
	updating mode.

	Returns True on successful configuration, False otherwise.

	"""

	returnValue = self.frameManager.enableTimeBasedMode(enable)

	if returnValue == None:
	    return False
	else:
	    return True

    def addParameterCallback(self, callback):
	"""Register a callback for parameter updates.

	The function should take two parameters, the first being the
	parameter ID, and the second being the value of the function

	"""
	self.parameterCallbacks.add(callback)

    def removeParameterCallback(self, callback):
	"""Remove a registered parameter callback function.

	Returns True if a parameter was found and removed,
	or False if the function was not registered.

	"""
	try:
	    self.parameterCallbacks.remove(callback)
	except KeyError:
	    return False

	return True

    def handleTimeBasedParameterUpdate(self, paramMap):
	for callback in self.parameterCallbacks:
	    callback(paramMap)

    def convertValueToReadableFormat(self, pid, incomingValue):
	value = math.floor(incomingValue)
	readableValue = "Invalid Input"

	if pid == 0x06: #Transmission
	    if value == 0:
		readableValue = "Unknown"
	    elif value == 1:
		readableValue = "Park"
	    elif value == 2:
		readableValue = "Neutral"
	    elif value == 3:
		readableValue = "Drive"
	    elif value == 4:
		readableValue = "Reverse"
	elif pid == 0x08 or pid == 0x09 or pid == 0x0A or pid == 0x0B or pid == 0x0E or pid == 0x1D or pid == 0x1F or pid == 0x20 or pid == 0x21:
	    if value == 0:
		readableValue = "On"
	    elif value == 1:
		readableValue = "Off"
	elif pid == 0x0F:
	    if value == 0:
		readableValue = "Yes"
	    elif value == 1:
		readableValue = "No"
	elif pid >= 0x10 and pid <= 0x1A:
	    if value == 0:
		readableValue = "Complete"
	    elif value == 1:
		readableValue = "Not Complete"
	elif pid == 0x1B:
	    if value == 0:
		readableValue = "Pressed"
	    elif value == 1:
		readableValue = "Not Pressed"
	elif pid == 0x1E:
	    if value == 0:
		readableValue = "Left"
	    elif value == 1:
		readableValue = "Right"
	    elif value == 2:
		readableValue = "Off"
	else:
	    readableValue = str(round(incomingValue, 2))

	return readableValue

