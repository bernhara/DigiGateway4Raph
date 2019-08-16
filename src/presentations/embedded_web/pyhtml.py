def content(request):
    """auto-generated from content.pyhtml"""
    import sys,string,cStringIO
    py_code=cStringIO.StringIO()
    import channels.channel_source_device_property as dev_props
    from common.types.boolean import Boolean
    from core.tracing import get_tracer
    _tracer = get_tracer("pyhtml")
    get_list = []
    for entry in request["sorted_table"]:
        device, channels = entry
        py_code.write("<div class=\"tab-content\">\n")
        py_code.write(" <div class=\"tab-content-heading\" onclick=\"$(\'")
        py_code.write(str(device))
        py_code.write("\').toggle();$(\'to-")
        py_code.write(str(device))
        py_code.write("\').toggle();$(\'tc-")
        py_code.write(str(device))
        py_code.write("\').toggle()\">\n")
        py_code.write("  <img style=\"display:none\" id=\'to-")
        py_code.write(str(device))
        py_code.write("\' alt=\"Tab Open\" src=\"/img/tabopen.gif\"/><img id=\'tc-")
        py_code.write(str(device))
        py_code.write("\' alt=\"Tab Close\" src=\"/img/tabclose.gif\"/>\n")
        py_code.write("   <h3 class=\"tab-selected\"> ")
        py_code.write(str(device))
        py_code.write("</h3>\n")
        py_code.write(" </div>\n")
        py_code.write("</div>\n")
        py_code.write(" <div style=\"display:none\" id=\"")
        py_code.write(str(device))
        py_code.write("\"> \n")
        py_code.write("  <table cellspacing=\"5\" cellpadding=\"0\">\n")
        py_code.write("  <tbody>\n")
        for entry in channels:
            py_code.write("    <tr>\n")
            py_code.write("      <td class=\"field-label\">\n")
            py_code.write(str(entry[0]))
            py_code.write(":\n")
            py_code.write("      </td>\n")
            py_code.write("      <td class=\"field-spacing\"> </td>\n")
            py_code.write("      <td class=\"field-input\">\n")
            py_code.write("        \n")
            chan_id = "%s.%s"%(device,entry[0])
            py_code.write("        <div id=\"fir-")
            py_code.write(str(chan_id))
            py_code.write("\" style=\"display:none\"></div>\n")
            chan = request["cm"].channel_get("%s.%s"%(device,entry[0]))
            path_loc = request["page_setting"]
            py_code.write("        \n")
            en = "style='border:none;padding-right:4px'"
            if chan.perm_mask() & dev_props.DPROP_PERM_SET:
                en="style='border:1px solid #007;padding-left:3px'"
            else:
                en=en+" onfocus='blur(this)' "
            py_code.write("       \n")
            if chan.type() == Boolean:
                py_code.write("            <div style=\"display:none\">\n")
                py_code.write("                <input type=\"text\" value=\"")
                py_code.write(str(entry[1]))
                py_code.write("\" maxlength=\"1\" size=\"1\" name=\"")
                py_code.write(str(entry[0]))
                py_code.write("\" id=\"ec-")
                py_code.write(str(chan_id))
                py_code.write("\" onfocus=\"blur(this)\"  />\n")
                py_code.write("            </div>\n")
                add1 = ""
                add2 = ""
                if chan.perm_mask() & dev_props.DPROP_PERM_SET:
                    add1 = "onclick=\"toggle(this);$('sf-%s').toggle();new Ajax.Updater('fir-%s','/%s?controller=set&own=ec-%s&val=0',{method:'get',evalScripts: true})  \""%(chan_id,chan_id,path_loc,chan_id)
                    add2 = "onclick=\"this.toggle();$('sn-%s').toggle();new Ajax.Updater('fir-%s','/%s?controller=set&own=ec-%s&val=1',{method:'get',evalScripts: true})  \""%(chan_id,chan_id,path_loc,chan_id)
                    get_list.append( str(chan_id) )
                elif chan.perm_mask() & dev_props.DPROP_PERM_GET and not (chan.options_mask() & dev_props.DPROP_OPT_DONOTDUMPDATA):
                    get_list.append( str(chan_id) )
                py_code.write("            <img style=\"display:none\" id=\'sn-")
                py_code.write(str(chan_id))
                py_code.write("\' src=\"/img/on.png\" ")
                py_code.write(str(add1))
                py_code.write(" />\n")
                py_code.write("            <img id=\'sf-")
                py_code.write(str(chan_id))
                py_code.write("\' src=\"/img/off.png\" ")
                py_code.write(str(add2))
                py_code.write(" />\n")
            else:
                py_code.write("            <input type=\"text\" value=\"")
                py_code.write(str(entry[1]))
                py_code.write("\" maxlength=\"64\" size=\"48\" name=\"")
                py_code.write(str(entry[0]))
                py_code.write("\" id=\"ec-")
                py_code.write(str(chan_id))
                py_code.write("\" ")
                py_code.write(str(en))
                py_code.write(" />\n")
                py_code.write("               \n")
                if chan.perm_mask() & dev_props.DPROP_PERM_GET and not (chan.options_mask() & dev_props.DPROP_OPT_DONOTDUMPDATA):
                    if not chan.perm_mask() & dev_props.DPROP_PERM_SET:
                        get_list.append( str(chan_id) )
                if chan.perm_mask() & dev_props.DPROP_PERM_SET:
                    py_code.write("                    <script>\n")
                    py_code.write("                       new Form.Element.Observer(\'ec-")
                    py_code.write(str(chan_id))
                    py_code.write("\', 1, \n")
                    py_code.write("                              function(element, value) {\n")
                    py_code.write("                                new Ajax.Updater(\'fir-")
                    py_code.write(str(chan_id))
                    py_code.write("\',\'/")
                    py_code.write(str(path_loc))
                    py_code.write("?controller=set&own=ec-")
                    py_code.write(str(chan_id))
                    py_code.write("&val=\'+$(\'ec-")
                    py_code.write(str(chan_id))
                    py_code.write("\').value,{method:\'get\',evalScripts: true})\n")
                    py_code.write("                               }\n")
                    py_code.write("                        )\n")
                    py_code.write("                    </script>\n")
                if chan.perm_mask() & dev_props.DPROP_PERM_REFRESH  and not (chan.options_mask() & dev_props.DPROP_OPT_DONOTDUMPDATA):
                    py_code.write("              <input type=button value=\"update\" \n")
                    py_code.write("                onclick=\"new Ajax.Updater(\'fir-")
                    py_code.write(str(chan_id))
                    py_code.write("\',\'/")
                    py_code.write(str(path_loc))
                    py_code.write("?controller=refresh&own=ec-")
                    py_code.write(str(chan_id))
                    py_code.write("\',{method:\'get\',evalScripts: true})\"/>\n")
            py_code.write("        <small id=\"ec-")
            py_code.write(str(chan_id))
            py_code.write(".debug\" style=\"color:red\"></small>\n")
            py_code.write("      </td>\n")
            py_code.write("    </tr>\n")
        py_code.write("  </tbody>\n")
        py_code.write("  </table>\n")
        py_code.write(" </div>\n")
    py_code.write("<div id=\"updatepanel\" style=\"display:none\"></div>\n")
    py_code.write("<script type=javascript>\n")
    py_code.write(" $(\'")
    py_code.write(str(request["sorted_table"][0][0]))
    py_code.write("\').toggle();\n")
    py_code.write(" $(\'to-")
    py_code.write(str(request["sorted_table"][0][0]))
    py_code.write("\').toggle();\n")
    py_code.write(" $(\'tc-")
    py_code.write(str(request["sorted_table"][0][0]))
    py_code.write("\').toggle();\n")
    py_code.write("new Ajax.PeriodicalUpdater(\'updatepanel\',\'/")
    py_code.write(str(path_loc))
    py_code.write("\',{method:\'post\', parameters: {own: \"")
    py_code.write(str(",".join(get_list)))
    py_code.write("\", controller:\"get_list\"}, evalScripts: true,frequency:2,decay:1})\n")
    py_code.write("a = ")
    py_code.write(str(get_list))
    py_code.write(";\n")
    py_code.write("for(i=0; i<a.length;i++){\n")
    py_code.write("   elem = $(\'ec-\'+a[i]);\n")
    py_code.write("   elem.focused = false;\n")
    py_code.write("   elem.hasFocus = function() {\n")
    py_code.write("      return this.focused;\n")
    py_code.write("   };\n")
    py_code.write("   elem.onfocus=function() {\n")
    py_code.write("      this.focused=true;\n")
    py_code.write("   };\n")
    py_code.write("   elem.onblur=function() {\n")
    py_code.write("      this.focused=false;\n")
    py_code.write("   };\n")
    py_code.write("}\n")
    py_code.write("</script>\n")
    return py_code

def get_list(request):
    """auto-generated from get_list.pyhtml"""
    import sys,string,cStringIO
    py_code=cStringIO.StringIO()
    py_code.write("<script>\n")
    from common.types.boolean import Boolean
    try:
        for e in  request["args"]['own'].split(","):
            py_code.write("		if(!$(\"ec-")
            py_code.write(str(e))
            py_code.write("\").hasFocus()){\n")
            sample = request["cm"].channel_get(e).get()
            py_code.write("			$(\"ec-")
            py_code.write(str(e))
            py_code.write("\").value = \"")
            py_code.write(str("%s %s" % (str(sample.value), sample.unit)))
            py_code.write("\";\n")
            py_code.write("			$(\"ec-")
            py_code.write(str(e))
            py_code.write(".debug\").innerHTML = \"\";\n")
            if request["cm"].channel_get(e).type() == Boolean:
                if request["cm"].channel_get(e).get().value:
                    py_code.write("	               $(\'sn-")
                    py_code.write(str(e))
                    py_code.write("\').show();\n")
                    py_code.write("	               $(\'sf-")
                    py_code.write(str(e))
                    py_code.write("\').hide();\n")
                else:
                    py_code.write("	               $(\'sn-")
                    py_code.write(str(e))
                    py_code.write("\').hide();\n")
                    py_code.write("	               $(\'sf-")
                    py_code.write(str(e))
                    py_code.write("\').show();          \n")
            py_code.write("    	}\n")
        py_code.write("	\n")
    except Exception,detail:
        py_code.write("	$(\"ec-")
        py_code.write(str(e))
        py_code.write("\").value = \"\";\n")
        py_code.write("	$(\"ec-")
        py_code.write(str(e))
        py_code.write(".debug\").innerHTML = \"")
        py_code.write(str(detail))
        py_code.write("\";\n")
    py_code.write("</script>\n")
    return py_code

def set(request):
    """auto-generated from set.pyhtml"""
    import sys,string,cStringIO
    py_code=cStringIO.StringIO()
    py_code.write("<script>\n")
    import digitime
    from samples.sample import Sample
    from common.types.boolean import Boolean
    import channels.channel_source_device_property as dev_props
    try:
        e = request["args"]['own']
        chan = request["cm"].channel_get(e[3:])
        val_type = chan.type()
        value = request["args"]["val"]
        if isinstance(value,Boolean) and not value:
            value = ""
        chan.consumer_set(Sample(digitime.time(), val_type(value) ))
        if chan.perm_mask() & dev_props.DPROP_PERM_GET and not (chan.options_mask() & dev_props.DPROP_OPT_DONOTDUMPDATA):
            py_code.write("		$(\"")
            py_code.write(str(e))
            py_code.write("\").value = \"")
            py_code.write(str(chan.get().value))
            py_code.write("\";\n")
            py_code.write("		$(\"")
            py_code.write(str(e))
            py_code.write(".debug\").innerHTML = \"\";\n")
        else:
            py_code.write("		$(\"")
            py_code.write(str(e))
            py_code.write("\").value = \"\";\n")
    except Exception, detail:
        py_code.write("	$(\"")
        py_code.write(str(e))
        py_code.write("\").value = \"\";\n")
        if request["args"].has_key("val") and not request["args"]["val"].split()=="":
            py_code.write("	   $(\"")
            py_code.write(str(e))
            py_code.write(".debug\").innerHTML = \"")
            py_code.write(str(detail))
            py_code.write("\";\n")
    py_code.write("</script>\n")
    return py_code

def get(request):
    """auto-generated from get.pyhtml"""
    import sys,string,cStringIO
    py_code=cStringIO.StringIO()
    py_code.write("<script>\n")
    from common.types.boolean import Boolean
    try:
        e = request["args"]['own']
        py_code.write(" \n")
        py_code.write("	$(\"")
        py_code.write(str(e))
        py_code.write("\").value = \"")
        py_code.write(str(str(request["cm"].channel_get(e[3:]).get().value)))
        py_code.write("\";\n")
        _tracer.info(str(request["cm"].channel_get(e[3:]).type()))
        if request["cm"].channel_get(e[3:]).type() == Boolean:
            if request["cm"].channel_get(e[3:]).get().value:
                py_code.write("	       $(\'sn-")
                py_code.write(str(e[3:]))
                py_code.write("\').show();\n")
                py_code.write("	       $(\'sf-")
                py_code.write(str(e[3:]))
                py_code.write("\').hide();\n")
            else:
                py_code.write("           $(\'sn-")
                py_code.write(str(e[3:]))
                py_code.write("\').hide();\n")
                py_code.write("           $(\'sf-")
                py_code.write(str(e[3:]))
                py_code.write("\').show();	       \n")
        py_code.write("	$(\"")
        py_code.write(str(e))
        py_code.write(".debug\").innerHTML = \"\";\n")
    except Exception,detail:
        py_code.write("	$(\"")
        py_code.write(str(e))
        py_code.write("\").value = \"\";\n")
        py_code.write("	$(\"")
        py_code.write(str(e))
        py_code.write(".debug\").innerHTML = \"")
        py_code.write(str(detail))
        py_code.write("\";\n")
    py_code.write("</script>\n")
    return py_code

def refresh(request):
    """auto-generated from refresh.pyhtml"""
    import sys,string,cStringIO
    py_code=cStringIO.StringIO()
    py_code.write("<script>\n")
    try:
        e = request["args"]['own']
        request["cm"].channel_get(e[3:]).consumer_refresh()
        py_code.write("	$(\"")
        py_code.write(str(e))
        py_code.write("\").value = ")
        py_code.write(str(request["cm"].channel_get(e[3:]).get().value))
        py_code.write(";\n")
        py_code.write("	$(\"")
        py_code.write(str(e))
        py_code.write(".debug\").value = \"\";\n")
    except Exception,detail:
        py_code.write("	$(\"")
        py_code.write(str(e))
        py_code.write("\").value = \"\";\n")
        py_code.write("	$(\"")
        py_code.write(str(e))
        py_code.write(".debug\").innerHTML = \"")
        py_code.write(str(detail))
        py_code.write("\";\n")
    py_code.write("</script>\n")
    return py_code

