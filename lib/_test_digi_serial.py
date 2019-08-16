import digi_serial

# use serial_device=0 for X4 direct RS-232 serial
# use serial_device=11 for X4 connected USB serial like FTDI

ser = digi_serial.SerialPort(serial_device=11, baud_rate=9600, 
                 stop_bits=1, data_bits=8, parity='N', flow_control='N')
                 
                 
if ser.open_port():
    print 'port was opened'
    ser.write("Hello there.")

    while True:
        buf = ser.read()
        print 'see: ', buf
        ser.write("Ho - don't say that!")

    ser.close_port()

else:
    print 'port failed to open, try rebooting?'

print "that's all folks"