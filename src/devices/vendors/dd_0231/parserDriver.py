import WirelessPacketParser
packetLength = 75
parser = WirelessPacketParser.WirelessPacketParser()
    
packetFile = open('packets.bin', 'rb')
packet = packetFile.read(packetLength)
count = 0
while(packet != ''):
    print('Parsing:' + str(count))
    count = count + 1
    #parse the packet
    parser.setExtendedPacket(packet)

    print (parser.macAddress, parser.serialNo, parser.dataField, parser.deviceId, parser.fields, parser.units, parser.types)
    #read the next packet
    packet = packetFile.read(packetLength)
packetFile.closed
