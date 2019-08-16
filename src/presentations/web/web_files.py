js = \
r"""
// Global variables:
var comment = {value: ""}; // Useful for debug

// Table: apply, name, time, value, refresh
var C_APPLY = 0;
var C_NAME = 1;
var C_TIME = 2;
var C_VALUE = 3;
var C_UNITS = 4;
//var C_REFRESH = 5;
var COL_NAMES = ['Apply', 'Channel', 'Timestamp', 'Value', 'Units'];
var TBL_HEADERS = 1;
var TBL_ID = 'channels_table';

// Permissions.  See DPROP_PERM_* from the DIA.  BUSY and CHECKED imply
// that the input field has focus (and hasn't just been sent), or that the
// "apply" checkbox has been checked.  There are also colors to indicate
// that the input field is BUSY, and won't be updated.
var GET = 1;
var SET = 2;
var REFR = 4;
var BUSY = 8;
var CHECKED = 16;
var BUSY_BG = '#9bffd3';   // Light "Digi" green
var NOT_BUSY_BG = 'white';

// Hold onto timeouts for auto_update().  There are two timeouts: one for
// when we get a response (short_update), and one for when we don't
// (long_update).  If we get a response, we request again after polling
// seconds, otherwise we multiply by LONG_UPDATE_SCALE.
var polling = 0;  // Set by load_table()
var short_update;
var LONG_UPDATE_SCALE = 5;
var long_update;

// Create three separate XMLHttpRequests, one each for auto_update(),
// send_changes(), and refresh_all()
var load_request;
var update_request;
var change_request;
var refresh_request;

// Quick shortcut to document.getElementById(id)
$ = function(id) {return document.getElementById(id);}

//========================================================================
// create_requests():
// Set up the XMLHttpRequest() variables.

function create_requests() {
   if( typeof XMLHttpRequest == 'undefined' ) {
      XMLHttpRequest = function() {
         try { return new ActiveXObject('Msxml2.XMLHTTP.6.0'); }
         catch(e) {}
         try { return new ActiveXObject('Msxml2.XMLHTTP.3.0') }
         catch(e) {}
         try { return new ActiveXObject('Msxml2.XMLHTTP') }
         catch(e) {}
         try { return new ActiveXObject('Microsoft.XMLHTTP') }
         catch(e) {}
         alert('This browser does not support\n'+
               'XMLHttpRequest.  Please use a\n'+
               'different DIA presentation.');
      }
   }
   load_request = new XMLHttpRequest();
   update_request = new XMLHttpRequest();
   change_request = new XMLHttpRequest();
   refresh_request = new XMLHttpRequest();
}

//========================================================================
// get_data(url):
// Request data from the server to build the table
function get_data(url) {
   create_requests();
   //comment = $('comment');
   load_request.open('GET', url, true);
   load_request.onreadystatechange = function() {
      if (load_request.readyState == 4 && load_request.status == 200) {
         if (load_request.responseText) {
            load_table(load_request.responseText);
         }
      }
   }
   load_request.send(null);
}

//========================================================================
// load_table(data):
//    Build the table based on the JSON structure, data, returned by the
//    server.  The JSON structure contains an with two fields:
//    - "settings" contains an object with the polling frequency,
//    - "devices" contains a list of devices, each of which contains 
//       - "name" of the device, and
//       - "channels", the channels support by the device, each of which
//          has a "name", "time" (timestamp), "value", and "unit" (units),
//          as well as a "perm" with the DIA permissions for that channel.
//
// load_table_headers(tblhd):
//    Given a pointer to the header row, fill that in based on COL_NAMES
//
// load_table_body(tbdy, devices):
//    Given a pointer to the table body, and a list of devices, populate
//    the device and channel rows in the table.

function load_table_headers(tblhd) {
   for (var i =0; i < COL_NAMES.length; ++i) {
      // Append a node _after_ the one we're updating ...
      tblhd.appendChild(tblhd.cells[0].cloneNode(true));
      var c = tblhd.cells[i]
      c.className = "column-header";
      c.align = "center";
      c.innerHTML = COL_NAMES[i];
   }
   // Give that extra node something to do
   c = tblhd.cells[i]
   c.className = "column-spacing";
   c.innerHTML = '&nbsp;';
}

function load_table_body(tbdy, devices) {
   for (var i in devices) {
      // Create row for device name
      var devname = devices[i]['name'];
      var row = tbdy.insertRow(tbdy.rows.length);
      var cell = row.insertCell(0);
      cell.colSpan = COL_NAMES.length + 1;
      cell.innerHTML = "<h3 class='page-separator'>"+devname+"</h3>";
      // Add channel rows and cells to the table
      channels = devices[i]['channels'];
      for (var j in channels) {
         row = tbdy.insertRow(tbdy.rows.length);
         for (var k in COL_NAMES) {
            row.insertCell(k).align='center';
         }
         var perm = channels[j]['perm'];
         var channel_name = channels[j]['name'];
         var name = devname+'.'+channel_name;
         var time = channels[j]['time'];
         var value = channels[j]['value'];
         var units = channels[j]['unit'];
         row.id = name;
         row.cells[C_APPLY].innerHTML = '<input type="hidden"' +
            ' id="'+name+'.set"' +
            ' value="'+perm+'">';
         if (perm & SET) {
            row.cells[C_APPLY].innerHTML += '<input type="checkbox"'+
               ' name="'+ name+'.apply' + '"id="' +name+'.apply'+ '"' +
               ' value="0"'+
               ' onclick="apply_click(this.id)"' +
               ' onkeypress="apply_keypress(event, this.id)"' +
               '>';
         }
         row.cells[C_NAME].innerHTML = channel_name;
         row.cells[C_TIME].innerHTML = time;
         row.cells[C_TIME].id = name+".time";
         if (perm & SET) {
            row.cells[C_VALUE].innerHTML = '<input type="text"'+
               ' name="'+name+'.value"'+
               ' onfocus="value_focus(this.id)"' +
               ' onblur="value_blur(this.id)"' +
               ' onkeydown="value_keydown(event, this.id)"' +
               ' onkeyup="value_keyup(event, this.id)"' +
               ' value="'+(perm&GET?value:"") +
               '" id="'+name+'.value">';
         } else if(perm & GET) {
            row.cells[C_VALUE].id = name+'.value';
            row.cells[C_VALUE].innerHTML = value;
         }
         if (units.length > 0) {
            row.cells[C_UNITS].innerHTML = units;
         }
      }
   }
}

function load_table(data) {
   var tbl = $(TBL_ID);
   // Note: using an eval() for JSON data can be dangerous.  The JSON sent
   // by the server (in this case) is fairly well sanitized (strings and
   // numbers only).  However, if the server were ever hijacked ....
   var datahash = eval('('+data+')');
   if (datahash['settings']['polling']) {
      polling = datahash['settings']['polling'];
   } else {
      polling = 0;
   }
   load_table_headers(tbl.tHead.rows[0]);
   load_table_body(tbl.tBodies[0], datahash['devices']);
   auto_update('%(page)s?=', update_request);
}

//========================================================================
// Event Handlers
// apply_*: event handler on the checkbox
// value_*: event handler on the input field

function apply_click(id) {
   var chkbx = $(id);
   var perm = $(id.replace('.apply', '.set'));
   var val = $(id.replace('.apply', '.value'));
   if (chkbx.checked) perm.value |= CHECKED;
   else perm.value &= ~CHECKED;
}

function apply_keypress(evnt, id) {
   var keynum;
   var chkbx = $(id);
   var perm = $(id.replace('.value', '.set'));
   var val = $(id.replace('.apply', '.value'));
   if(window.event) { keynum = evnt.keyCode; } // IE
   else if(evnt.which) { keynum = evnt.which; } // Netscape/Firefox/Opera
   keychar = String.fromCharCode(keynum);
   if (keychar == '\n' || keychar == '\r') {
      val.savValue = val.value;
      if (chkbx.checked) perm.value |= CHECKED;
      else perm.value &= ~CHECKED;
      send_changes();
   }
}

function value_focus(id) {
   var val = $(id);
   var perm = $(id.replace('.value', '.set'));
   perm.value |= BUSY;
   if ( ! (perm.value & CHECKED)) val.savValue = val.value;
   val.style.backgroundColor=BUSY_BG;
}

function value_blur(id) {
   var val = $(id);
   var perm = $(id.replace('.value', '.set'));
   var chkbx = $(id.replace('.value', '.apply'));
   if (chkbx.checked) perm.value |= CHECKED;
   else perm.value &= ~CHECKED;
   perm.value &= ~BUSY;
   val.style.backgroundColor=NOT_BUSY_BG;
}

function value_keydown(evnt, id) {
   var keynum;
   var val = $(id);
   var perm = $(id.replace('.value', '.set'));
   var chkbx = $(id.replace('.value', '.apply'));
   if(window.event) { keynum = evnt.keyCode; }  // IE
   else if(evnt.which) { keynum = evnt.which; } // the rest ...
   keychar = String.fromCharCode(keynum);
   if (keychar == '\n' || keychar == '\r') {
      val.savValue = val.value;
      perm.value |= CHECKED;
      perm.value &= ~BUSY;
      val.style.backgroundColor=NOT_BUSY_BG;
      chkbx.checked = true;
      send_changes();
   } else {
      perm.value |= BUSY;
      val.style.backgroundColor=BUSY_BG;
   }
}

function value_keyup(evnt, id) {
   var keynum;
   var val = $(id);
   var perm = $(id.replace('.value', '.set'));
   var chkbx = $(id.replace('.value', '.apply'));
   if(window.event) { keynum = evnt.keyCode; }  // IE
   else if(evnt.which) { keynum = evnt.which; } // the rest ...
   keychar = String.fromCharCode(keynum);
   if (val.value != val.savValue) {
      chkbx.checked = true;
   }
}

//========================================================================
// Asynchronous happenings:
//
// apply_get(data):
//    Receive the JSON structure, data, from the server, and update all of
//    the channels, as long as they are not currently BUSY (cursor in a text
//    input) or CHECKED (input checkbox is checked).  Note that BUSY and
//    CHECKED are stored in the hidden perm input.
//
// send_changes():
//    Look through the table, and gather fields with CHECKED in the hidden
//    perm input.  Calls auto_update() to send request.
//
// refresh_all():
//    Send a refresh_all request to the server to have it query the
//    device.  Calls auto_update() to send request.
//
// auto_update(command, xml_request_handler):
//    Sends the command as the URL, and uses the xml_request_handler to
//    wait for the callback.  If polling is enabled, we start (or
//    continue) with auto updates of the table data.  Uses a callback to
//    apply_get() to update the table.

function apply_get(data) {
   var c;
   datahash = eval('('+data+')');
   devices = datahash['devices'];
   for (var d in devices) {
      device = devices[d];
      dname = device['name'];
      for (c in device['channels']) {
         channel = device['channels'][c];
         name = dname+'.'+channel['name'];
         perm = $(name+'.set').value;
         val = $(name+'.value');
         time = $(name+'.time');
         // Only update when GET, or ! BUSY (no cursor in field), and ! CHECKED
         if ((perm & SET) && (perm & GET) && !(perm & BUSY) && 
               !(perm & CHECKED)) {
            val.savValue = 
                  val.value = channel['value'];
            time.innerHTML = channel['time'];
         } else if (perm & GET && !(perm & SET)) {
            val.innerHTML = channel['value'];
            time.innerHTML = channel['time'];
         }
         // Hmm.  If the value is not GETable, should we clear it on
         // apply? what about update (when it isn't checked, of course)?
      }
   }
}

function send_changes() {
   var tbl = $(TBL_ID);
   var update_str = '';
   for (i = TBL_HEADERS; i < tbl.rows.length; ++i) {
      var row=tbl.rows[i];
      if (row.id) {
         if($(row.id+'.set').value & SET) {
            if ($(row.id+'.apply').checked) {
               var value = $(row.id+'.value').value;
               update_str += (update_str?'&':'')+ escape(row.id)+'='+ 
                     escape(value);
               $(row.id+'.apply').checked = false;
               $(row.id+'.set').value &= ~CHECKED;
            }
         }
      }
   }
   if (update_str) {
      auto_update('%(page)s?' + update_str, change_request);
   }
}

function refresh_all() {
   auto_update('%(page)s?=refresh_all', refresh_request);
}

function auto_update(command, request) {
   // If we're here, we can cancel outstanding update requests:
   clearTimeout(short_update);
   clearTimeout(long_update);
   request.open('GET', command, true);
   request.onreadystatechange = function() {
      if (request.readyState == 4 && request.status == 200) {
         if (request.responseText) {
            apply_get(request.responseText);
            if (polling) {
                  short_update = setTimeout("auto_update('%(page)s?=', update_request)",
                        polling*1000);
            }
         }
      } else if (request.readyState == 4 && request.status != 200) {
         // Assume something has happened to the server, but that it
         // will be back -- wait a bit before the next request.
         if (polling) {
            long_update = setTimeout("auto_update('%(page)s?=', update_request)",
                     polling*1000*LONG_UPDATE_SCALE);
         }
      }
   }
   request.send(null);
}
//<--END-->
"""

html = \
r"""
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
<meta http-equiv='Content-Type' content='text/html; charset=iso-8859-1'>
<title>%(title)s</title>
<link rel="stylesheet" href="/style/stylesheet.css" type="text/css">

<script type="text/javascript" language="javascript">
//<!-- %(js)s
//-->
</script>
</head>
<body onload="get_data('%(page)s?=get_data')">

<!--textarea id="comment" cols="22" rows="43"
   style='position:absolute; left:0; top: 0;'
></textarea-->
<div id='page-content-body' style='position:absolute; left:200px;'>
   <div class='page-heading' style=''>
      <h2>Web Configuration</h2>
   </div>
   <div class='page-htmlcontent'>
      <div class='tab-content'>
         <div class='tab-content-heading' style=''>
            <h3 class='tab-selected'> Manage channels</h3>
         </div>
         <div class='tab-content-body'>
            <table id='channels_table' class='page-content-table' 
                  cellspacing='0' cellpadding='0' summary="column headers">
               <thead>
                  <tr>
                     <th class='column-header' align=center> &nbsp; </th>
                  </tr>
               </thead>
               <tbody>
               </tbody>
            </table>
            <div class='form-buttons'>
               <div class='standard-custom'>
               <table width="740" summary="channels">
               <tr>
                  <td align="left">
                     <INPUT TYPE='button' NAME='save' VALUE='Apply Changes'
                           onclick="send_changes()">
                  <td align="right">
                     <INPUT TYPE='button' NAME='save' VALUE='Refresh All'
                           onclick="refresh_all()">
               </tr>
               </table>
               </div>
            </div>
         </div>
      </div>
   </div>
</div>
</body>
</html>
<!--END-->
""" % {"page":'%(page)s', "title":'%(title)s', "js":js} # (title, js)

