import struct

try:
    import devices.vendors.dd_0231.RecordParser as RecordParser
except:
    import RecordParser

class WirelessPacketParser:
    """A parser for parsing point six wireless packets"""
    ACK = struct.pack("BBBB", 0xc3, 0x3c, 0x00, 0x06)
    ACK_REQ_CONF = struct.pack("BBBB", 0xc3, 0x3c, 0x00, 0x07)

    FILTER=''.join([(len(repr(chr(x)))==3) and chr(x) or '.' for x in range(256)])

    KEY_ALARM_EXIT = 'alarmExit'
    KEY_CLOCK = 'clock'
    KEY_COMMAND = 'command'
    KEY_DEVICE_ID = 'deviceId'
    KEY_DOOR_OPEN = 'doorOpen'
    KEY_FIRMWARE_VERSION = 'firmwareVersion'
    KEY_HI_VAL1 = 'highValue1'
    KEY_HI_TIME1 = 'highTime1'
    KEY_HI_VAL2 = 'highValue2'
    KEY_HI_TIME2 = 'highTime2'
    KEY_HYSTERISIS = 'hysterisis'
    KEY_LO_VAL1 = 'lowValue1'
    KEY_LO_TIME1 = 'lowTime1'
    KEY_LO_VAL2 = 'lowValue2'
    KEY_LO_TIME2 = 'lowTime2'
    KEY_LOG_PERIOD = 'logPeriod'
    KEY_SER_NO = 'Serial Number'
    KEY_TRIES = 'tries'
    KEY_XMIT_PERIOD = 'xmit_period'
 
    LONG_SERIAL = 'LONG_SERIAL'
 
    TC16 = 'TC16'
    TC16_MIDPOINT = 0x7fff
    TC16_OFFSET = -32769

    TYPE_ANALOG = "analog"
    TYPE_COUNT = "count"
    TYPE_HUMIDITY = "humidity"
    TYPE_PRESSURE = "pressure"
    TYPE_TEMPERATURE = "temperature"

    UNITS_CELSIUS = "C"
    UNITS_COUNT = "Count"
    UNITS_PER_CENT_RH = "%RH"
    UNITS_UNITS = "Units"

    _p6id = int('c33c', 16)
    _andMask1 = 0xfffffffc
    _andMask2 = 3
    _andMaskLocalConfigure = 1
    _andMaskLowBatt = 4
    _andMaskLinePower = 0x10
    _conversionMaps = None
    _datamaps = None
    _eeumaps = None
    _servicemaps = None
    _typemaps = None
    _unitmaps = None

    def __init__(self):
        """initialize the maps"""
        if self._datamaps is None:
            self._conversionMaps = {}
            self._datamaps = {}
            self._eeumaps = {}
            self._littleEndian = {}
            self._servicemaps = {}
            self._typemaps = {}
            self._unitmaps = {}

            #build conversion maps
            #offset and scale for each I/O point for that device
            conversionMap = [0, 0.0244, -40, 0.030525]
            self._conversionMaps['51'] = conversionMap
            self._conversionMaps['52'] = conversionMap

            #use two's complement for this device
            conversionMap = [self.LONG_SERIAL, 0, self.TC16, 1.0/16.0]
            self._conversionMaps['53'] = conversionMap
            self._conversionMaps['54'] = conversionMap

            #set up little endian
            self._littleEndian['10'] = True
            self._littleEndian['11'] = True

            #build the data maps
            datamap = '000000111111'
            self._datamaps['10'] = datamap
            self._datamaps['11'] = datamap

            datamap = '990011112222'
            self._datamaps['28'] = datamap
            self._datamaps['29'] = datamap

            datamap = '999900001111'
            self._datamaps['51'] = datamap
            self._datamaps['52'] = datamap

            datamap = '000000001111'
            self._datamaps['53'] = datamap
            self._datamaps['54'] = datamap

            datamap = '001122223333'
            self._datamaps['75'] = datamap
            self._datamaps['76'] = datamap

            #build the Enumerated Egnineering Maps
            #each entry contains offset and scale
            eeumap = [0, 0.0244, '%']
            self._eeumaps['00'] = eeumap
            eeumap = [-1, 0.00732, 'InH20']
            self._eeumaps['51'] = eeumap
            eeumap = [-25.03, 0.0336, '%']
            self._eeumaps['52'] = eeumap
            eeumap = [0, 0.244, 'mips']
            self._eeumaps['53'] = eeumap
            eeumap = [0, 1.465, 'mg']
            self._eeumaps['54'] = eeumap
            eeumap = [0, 0.732, 'Amps']
            self._eeumaps['55'] = eeumap
            eeumap = [0, 0.005, 'Amps']
            self._eeumaps['56'] = eeumap
            eeumap = [-55, 0.0500, 'C']
            self._eeumaps['57'] = eeumap
            eeumap = [0, 0.00610, '%']
            self._eeumaps['58'] = eeumap
            eeumap = [0, 0.0671, 'ppm']
            self._eeumaps['59'] = eeumap
            eeumap = [-200, 0.0977, 'C']
            self._eeumaps['60'] = eeumap
            eeumap = [0, 0.0244, '%RH']
            self._eeumaps['61'] = eeumap
            eeumap = [-40, 0.0549, 'F']
            self._eeumaps['62'] = eeumap
            eeumap = [-40, 0.030525, 'C']
            self._eeumaps['63'] = eeumap

            #build the service flag maps
            self._servicemaps['10'] = True
            self._servicemaps['11'] = False

            self._servicemaps['28'] = True
            self._servicemaps['29'] = False

            self._servicemaps['51'] = True
            self._servicemaps['52'] = False

            self._servicemaps['53'] = True
            self._servicemaps['54'] = False

            self._servicemaps['75'] = True
            self._servicemaps['76'] = False

            #build the type maps
            typemap = [self.TYPE_COUNT, self.TYPE_COUNT]
            self._typemaps['10'] = typemap
            self._typemaps['11'] = typemap

            typemap = [self.TYPE_COUNT, self.TYPE_ANALOG]
            self._typemaps['28'] = typemap
            self._typemaps['29'] = typemap

            typemap = [self.TYPE_HUMIDITY, self.TYPE_TEMPERATURE]
            self._typemaps['51'] = typemap
            self._typemaps['52'] = typemap

            typemap = [self.TYPE_TEMPERATURE]
            self._typemaps['53'] = typemap
            self._typemaps['54'] = typemap

            typemap = [self.TYPE_ANALOG, self.TYPE_ANALOG]
            self._typemaps['75'] = typemap
            self._typemaps['76'] = typemap

            #build the unit maps
            unitmap = [self.UNITS_COUNT, self.UNITS_COUNT]
            self._unitmaps['10'] = unitmap
            self._unitmaps['11'] = unitmap

            unitmap = [self.UNITS_COUNT, self.UNITS_UNITS]
            self._unitmaps['28'] = unitmap
            self._unitmaps['29'] = unitmap

            unitmap = [self.UNITS_PER_CENT_RH, self.UNITS_CELSIUS]
            self._unitmaps['51'] = unitmap
            self._unitmaps['52'] = unitmap

            unitmap = [self.UNITS_CELSIUS]
            self._unitmaps['53'] = unitmap
            self._unitmaps['54'] = unitmap

            unitmap = [self.UNITS_UNITS, self.UNITS_UNITS]
            self._unitmaps['75'] = unitmap
            self._unitmaps['76'] = unitmap

        #initialize instance data
        self.identifier = 0
        self.command = 0
        self.packetCount = 0
        self.macAddress = ''
        self.clock = 0
        self.logNext = 0
        self.rssi = 0
        self.reserved = 0
        self.locator1 = 0
        self.locator2 = 0
        self.hexAsciiData = ''
        self.originator = 0
        self.batteryCount = 0
        self.maxBatteryCount = 0
        self.period = 0
        self.alarm = 0
        self.status = 0
        self.quality = 0

        self.deviceId = 0
        self.serialNo = 0
        self.dataField = 0
        self.fields = []
        self.service = False
        self.types = []
        self.units = []

        #create record factories
        #this is just for the header portion
        self._headerFactory = RecordParser.RecordFactory("""
            >H.id
            >H.cmd
            71s.payload
""")

        #payload portion for beacon data
        self._beaconFactory = RecordParser.RecordFactory("""
            >H.packetCount
            18s.mac
            >I.clock
            >H.logNext
            1B.rssi
            1B.reserved
            c.locator1
            c.locator2
            29s.payload
            1B.org
            3B.batteryCount
            3B.maxBatteryCount
            >H.period
            1B.alarm
            1B.status
            1B.quality
""")

        #payload portion for config data
        self._configFactory = RecordParser.RecordFactory("""
            >I.serNo
            >H.xmitPeriod
            1B.reserved1
            1B.reserved2
            1B.alarmExit
            1B.tries
            1B.hysterisis
            1B.logPeriod
            >I.clock
            >I.firmwareVersion
            6B.reserved3
            >H.highValue1
            1B.highTime1
            >H.lowValue1
            1B.lowTime1
            4B.reserved4
            >H.highValue2
            1B.highTime2
            >H.lowValue2
            1B.lowTime2
            4B.reserved5
""")

        return

    def dump(self, src, length=8):
        """classic three column dump of a hex string"""
        N=0; result=''
        while src:
           s,src = src[:length],src[length:]
           hexa = ' '.join(["%02X"%ord(x) for x in s])
           s = s.translate(self.FILTER)
           result += "%04X   %-*s   %s\n" % (N, length*3, hexa, s)
           N+=length
        return result

    def convertBytesToInt(self, bytes):
        """Make an int out of a group of bytes"""
        result = 0
        for idx in range(len(bytes)):
            if idx == 0:
                result = int(bytes[0])
            else:
                result = (result << 8) + bytes[idx]

        return result

    def convertSigned16(self, val):
        """do two's complement 16 bit processing"""
        if val > self.TC16_MIDPOINT:
            val = val - self.TC16_MIDPOINT + self.TC16_OFFSET
        return val

    def customConvert(self):
        """convert data to engineering units if appropriate"""
        try:
            conversionMap = self._conversionMaps[str(self.deviceId)]

            convertIdx = 0
            for idx in range(len(self.fields)):
                offset = conversionMap[convertIdx]
                scale = conversionMap[convertIdx + 1]

                if(offset!=None):
                    if(str(offset) == self.TC16):
                        val = self.fields[idx]
                        val = self.convertSigned16(val) * scale
                    elif(str(offset) == self.LONG_SERIAL):
                        #merge with the existing serial number
                        val = self.serialNo << 32
                        val |= self.fields[idx]
                        self.serialNo = val
                    else:
                        val = (self.fields[idx] * scale) + offset

                    self.fields[idx] = val

                convertIdx += 2

        except KeyError:
            #no conversion for this type
            None

        return

    def buildConfig(self, serNo, xmit_period, alarm_exit, tries, hysterisis, log_period,
                    high_value1, high_time1, low_value1, low_time1,
                    high_value2, high_time2, low_value2, low_time2):
        """create the configuration packet"""
        devId = self.deviceId
        eeu1 = None
        eeu2 = None
        if devId == '28' or devId == '29':
            eeu1 = self.eeu1
        elif devId == '51' or devId == '52':
            eeu1 = self._eeumaps[str(61)]
            eeu2 = self._eeumaps[str(63)]
        elif devId == '53' or devId == '54':
            high_value1 /= 16
            low_value1 /= 16
            hysterisis /= 16
        elif devId == '75' or devId == '76':
            eeu1 = self.eeu1
            eeu2 = self.eeu2

        #convert engineering units as appropriate
        if eeu1 is not None:
            high_value1 = (high_value1 / eeu1[1]) - eeu1[0]
            low_value1 = (low_value1 / eeu1[1]) - eeu1[0]
            hysterisis = (hysterisis / eeu1[1]) - eeu1[0]
        if eeu2 is not None:
            high_value2 = (high_value2 / eeu2[1]) - eeu2[0]
            low_value2 = (low_value2 / eeu2[1]) - eeu2[0]
        #convert the log period from seconds to 30 second intervals
        log_period /= 30
 
        packet = '\xC3\x3C\x00\x08' + struct.pack(">IHBBBBBBIIIHHBHBIHBHBIqqqH",
                                                  serNo, xmit_period, 0, 0,
                                                  alarm_exit, tries, hysterisis, log_period,
                                                  0,0,0,0,
                                                  high_value1, high_time1, low_value1, low_time1,
                                                  0, high_value2, high_time2, low_value2,
                                                  low_time2, 0, 0, 0, 0, 0)
        print ("config packet:" + self.dump(packet))
        return packet

    def convertLittleEndian(self):
        """Some conversions need special attention. This takes care of them."""
        devId = str(self.deviceId)
        if self._littleEndian.get(devId, False):
            revFields = []
            for field in self.fields:
                revFields.append(self.reverseByteOrder(field))
            self.fields = revFields

    def extendedConvert(self):
        """Some conversions need special attention. This takes care of them."""
        devId = str(self.deviceId)
        if(devId == '28' or devId == '29'):
          answers = []
          #just add the counter value
          answers.append(self.fields[1])
          #find the engineering units converter
          enum = self.fields[0] & 0x3F
          #look up the scale and offset for that eeu
          eeu = self._eeumaps[str(enum)]
          self.eeu1 = eeu
          print('eeu:' + str(eeu))
          #convert from twos complement and adjust by scale/offset
          val = (self.convertSigned16(self.fields[2]) * eeu[1]) + eeu[0]
          answers.append(val)
          #reset fields to hold the new answers
          self.fields = answers
          self.units = [self.UNITS_COUNT, eeu[2]]
        elif(devId == '53' or devId == '54'):
          #strip off the first part of the answer which is the last part of the
          #serial number
          answers = [self.fields[1]]
          self.fields = answers
        elif(devId == '75' or devId == '76'):
          answers = []
          #find out the number of I/O points
          pointCount = self.fields[0] & 3
          #find out engineering units for 1st I/O
          enum = self.fields[1] & 0x3F
          eeu = self._eeumaps[str(enum)]
          self.eeu1 = eeu
          #new value = old value * scale + offset
          val = (self.convertSigned16(self.fields[3]) * eeu[1]) + eeu[0]
          answers.append(val)
          self.units = [eeu[2]]
          #see if there's two
          if pointCount == 2:
              #find out engineering units for 2nd I/O
              #and off first two bits
              enum = self.fields[0] >> 2
              eeu = self._eeumaps[str(enum)]
              self.eeu2 = eeu
              val = (self.convertSigned16(self.fields[2]) * eeu[1]) + eeu[0]
              answers.append(val)
              self.units.append(eeu[2])
          else:
              self.eeu2 = []
          #reset fields to hold the new answers
          self.fields = answers

        return

    def parseBeacon(self, packetPayload):
        """Parse the beacon data from the payload section of the packet"""
        record = self._beaconFactory.build(packetPayload)
        self.packetCount = record.packetCount
        self.macAddress = record.mac[:-1]
        self.clock = record.clock
        self.logNext = record.logNext
        self.rssi = record.rssi
        self.reserved = record.reserved
        self.locator1 = record.locator1
        self.locator2 = record.locator2
        self.hexAsciiData = record.payload
        self.originator = record.org
        self.batteryCount = self.convertBytesToInt(record.batteryCount)
        self.maxBatteryCount = self.convertBytesToInt(record.maxBatteryCount)
        self.period = record.period
        self.alarm = record.alarm
        self.status = record.status
        self.quality = record.quality
 
        #parse the standard packet
        self.deviceId = self.hexAsciiData[0:2]
        #extract the serial number from the next 30 bits
        #by pulling the next 8 nybbles
        work = long(self.hexAsciiData[2:10], 16)
        #and off the last two bits of the serial number
        self.serialNo = work & self._andMask1
        #pull the rest and store as the open flag
        doorOpen = ((work & self._andMask2) == 1)
        #pull the 48 bit data field
        work = self.hexAsciiData[10:22]
        self.dataField = work
        self.parseDataField()

        values = {}
        values[self.KEY_DOOR_OPEN] = doorOpen
        values['packetCount'] = self.packetCount
        values['macAddress'] = self.macAddress
        values[self.KEY_CLOCK] = self.clock
        values['logNext'] = self.logNext
        values['rssi'] = self.rssi
        values['reserved'] = self.reserved
        values['locator1'] = self.locator1
        values['locator2'] = self.locator2
        values['hexAsciiData'] = self.hexAsciiData
        values['originator'] = self.originator
        values['batteryCount'] = self.batteryCount
        values['maxBatteryCount'] = self.maxBatteryCount
        values['period'] = self.period
        values['alarm'] = self.alarm
        values['status'] = self.status
        values['quality'] = self.quality

        values[self.KEY_DEVICE_ID] = self.deviceId
        values[self.KEY_SER_NO] = self.serialNo
        values['dataField'] = self.dataField
        values['fields'] = self.fields
        values['service'] = self.service
        values['types'] = self.types
        values['units'] = self.units

        #parse the status
        values['locallyConfigured'] = ((self.status & self._andMaskLocalConfigure) == self._andMaskLocalConfigure)
        values['lowBattery'] = ((self.status & self._andMaskLowBatt) == self._andMaskLowBatt)
        values['linePowered'] = ((self.status & self._andMaskLinePower) == self._andMaskLinePower)

        return values

    def parseConfig(self, packetPayload):
        record = self._configFactory.build(packetPayload)
        values = {}
        values[self.KEY_SER_NO] = record.serNo
        values[self.KEY_XMIT_PERIOD] = record.xmitPeriod
        values[self.KEY_ALARM_EXIT] = record.alarmExit
        values[self.KEY_TRIES] = record.tries
        values[self.KEY_HYSTERISIS] = record.hysterisis
        values[self.KEY_LOG_PERIOD] = record.logPeriod
        values[self.KEY_CLOCK] = record.clock
        values[self.KEY_FIRMWARE_VERSION] = record.firmwareVersion
        values[self.KEY_HI_VAL1] = record.highValue1
        values[self.KEY_HI_TIME1] = record.highTime1
        values[self.KEY_LO_VAL1] = record.lowValue1
        values[self.KEY_LO_TIME1] = record.lowTime1
        values[self.KEY_HI_VAL2] = record.highValue2
        values[self.KEY_HI_TIME2] = record.highTime2
        values[self.KEY_LO_VAL2] = record.lowValue2
        values[self.KEY_LO_TIME2] = record.lowTime2

        return values

    def parseDataField(self):
        """Parse the standard data field according to the identifier type"""
        devId = str(self.deviceId)
        datamap = self._datamaps[devId]
        work = ''
        dataIndex = 0
        fieldIndex = 0
        mapIndex = 0
        self.fields=[]
        while mapIndex < len(datamap):
            mapChar = datamap[mapIndex]
            mapValue = int(mapChar)
            if fieldIndex == mapValue:
                #we've found another character in our current field
                work = work + self.dataField[dataIndex]
                mapIndex = mapIndex + 1
                dataIndex = dataIndex + 1
            elif fieldIndex+1 == mapValue:
                #we've found the end of the field we're working on
                self.fields.append(int(work, 16))
                work = ''
                fieldIndex = fieldIndex + 1
            else:
                if len(work) > 0:
                    self.fields.append(int(work, 16))
                    work = ''
                    fieldIndex = fieldIndex + 1
                mapIndex = mapIndex + 1
                dataIndex = dataIndex + 1

        if len(work) > 0:
            self.fields.append(int(work, 16))

        self.service = self._servicemaps[devId]
        self.types = self._typemaps[devId]
        self.units = self._unitmaps[devId]

        self.customConvert()
        self.extendedConvert()
        self.convertLittleEndian()

        return

    def parseExtendedPacket(self, packet, values=None):
        if values==None:
            values = {}

        """receive and parse the extended packet"""
        #create the record
        record = self._headerFactory.build(packet)
        #parse the identifier
        self.identifier = record.id
        #check the indentifier
        if(self._p6id!=self.identifier):
            raise ValueError('Not a P6 packet:' + str(self.identifier))

        #parse the rest of the extended packet
        self.command = record.cmd

        if self.command == 2 or self.command == 5:
            values = self.parseBeacon(record.payload)
        elif self.command == 0x10:
            values = self.parseConfig(record.payload)

        values[self.KEY_COMMAND] = self.command
        return values

    def parseHysterisis(self, hysterisis):
        """convert percentage forms of hysterisis to a integer value"""
        s1 = str(hysterisis)
        if s1.endswith('%'):
            hysterisis = float(s1[:-1])
            hysterisis = round(40.95 * hysterisis)
        else:
            hysterisis = round(hysterisis)
 
        return hysterisis

    def reverseByteOrder(self, data):
        """
        Method to reverse the byte order of a given unsigned data value
        Input:
            data:   data value whose byte order needs to be swap
                    data can only be as big as 4 bytes
        Output:
            revD: data value with its byte order reversed
        """
        s = "Error: Only 'unsigned' data of type 'int' or 'long' is allowed"
        if not ((type(data) == int)or(type(data) == long)):
            s1 = "Error: Invalid data type: %s" % type(data)
            print(''.join([s,'\n',s1]))
            return data
        if(data < 0):
            s2 = "Error: Data is signed. Value is less than 0"
            print(''.join([s,'\n',s2]))
            return data
    
        seq = ["0x"]
    
        while(data > 0):
            d = data & 0xFF     # extract the least significant(LS) byte
            seq.append('%02x'%d)# convert to appropriate string, append to sequence
            data >>= 8          # push next higher byte to LS position
    
        revD = int(''.join(seq),16)
    
        return revD
     