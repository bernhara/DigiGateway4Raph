from xbee_string import *
class XBeeNamedAttributes(XBeeString):
    # Some helper dictionaries to convert from strings to whatevers:
    types = {
        'str': str,
        'int': int,
        'float': float,
        'real': float,
        'double': float,
    }
    
    initial = {
        'str': "",
        'int': 0,
        'float': 0.0,
        'real': 0.0,
        'double': 0.0,
    }

    perms = {
        'gettable': (DPROP_PERM_GET|DPROP_PERM_REFRESH),
        'settable': (DPROP_PERM_GET|DPROP_PERM_SET|DPROP_PERM_REFRESH),
    }

    # Override the appropriate methods
    # __init__() needs to know about the attribute setting
    def __init__(self, name, core_services):
        new_setting = [
            {'name': 'attributes', 'type': dict, 'required': True},
            {'name': 'poll_rate', 'type': float, 'required': False},
            ]
        XBeeString.__init__(self, name, core_services,
                extra_settings = new_setting,
                create_local = False,
                create_remote = False)

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

    # apply_settings() is fine
    # start() needs a bit of work
    def start(self):
        self.attrs = SettingsBase.get_setting(self, "attributes")
        for name in self.attrs:
            # Handle 3, 2, or 1 setting in the list.
            if len(self.attrs[name]) == 3:
               type_, perm_, init_, = self.attrs[name]
            elif len(self.attrs[name]) == 2:
               type_, perm_, = self.attrs[name]
               init_ = self.initial[type_]
            elif len(self.attrs[name]) == 1:
               type_, = self.attrs[name]
               perm_ = "gettable"
               init_ = self.initial[type_]
            else:
               self.__tracer.error("length of attribute options is " + \
                      "%s, should be 1, 2, or 3", len(self.attrs[name]))

            # Make sure init_ is the right type
            # XXX dc: Should this be a try:/except: block?
            init_ = self.types[type_](init_)

            if perm_ == 'gettable':
                refresh = lambda ntmp=name: self.request_str(ntmp)
                set = lambda: None
            elif perm_ == 'settable':
                refresh = lambda ntmp=name: self.request_str(ntmp)
                set = lambda sample, ntmp=name: self.set_and_send(ntmp, sample)

            self.add_property(
                ChannelSourceDeviceProperty(name=name, type=self.types[type_],
                initial=Sample(timestamp=0, value=init_),
                perms_mask=self.perms[perm_],
                options=DPROP_OPT_AUTOTIMESTAMP,
                refresh_cb = refresh,
                set_cb = set
                    )
                )

        XBeeString.start(self)

    def receive_data(self, buf, addr):
        # Parse the I/O sample, and see if it applies to a named channel
        colon = buf.find(':')
        bang = buf.find('!')
        if colon > 0 and (bang < 0 or colon < bang):
            # verify attribute is in channels
            name = buf[:colon]
            try:
                attr = self.attrs[name]
            except:
                # Un - Silently ignore bad names
                attr = []
                self.__tracer.error("Channel not found: ", name)
                pass
            if attr:
                value = self.types[attr[0]](buf[colon+1:])
                self.property_set(name, Sample(digitime.time(), value))
            else:
                self.__tracer.info("self.attrs['%s'] is '%s'", name, attr)
        elif bang > 0:
            # XXX dc: do something reasonable here.  Right now, we just
            # ignore the set value.
            self.__tracer.error("Illegal value or channel: '%s'", buf)
        else:
            self.__tracer.error("Unrecognized string: '%s'", buf)

    def set_and_send(self, name, sample_):
        buf = "%s=%s" % (name, sample_.value)
        self.__tracer.info("set_and_send: '%s'", buf)
        # Set time to 0.  We've set the sample, but not received a
        # response
        self.property_set(name, Sample(0, sample_.value))
        self._XBeeString__xbee_manager.xbee_device_xmit(
            # src_ep, 'name=value', addr
            self.endpoint, buf, self.remote_mepc)
        
    def request_str(self, name):
        buf = "%s?" % name
        self._XBeeString__xbee_manager.xbee_device_xmit(
            # src_ep, 'name=value', addr
            self.endpoint, buf, self.remote_mepc)

    def __schedule_refresh(self):
        poll_secs = SettingsBase.get_setting(self, "poll_rate")
        if poll_secs:
            self._XBeeString__xbee_manager.xbee_device_schedule_after(
                    poll_secs, self.__schedule_refresh)
        # '*' requests an update on all channels
        self.request_str('*')

    def running_indication(self):
        poll_secs = SettingsBase.get_setting(self, "poll_rate")
        if poll_secs:
            self.__tracer.info("Scheduling refreshes every %.2f seconds", poll_secs)
            self.__schedule_refresh()
        else:
            self.__tracer.warning("No refresh polling")
