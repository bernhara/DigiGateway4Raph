############################################################################
#                                                                          #
# Copyright (c)2008, 2009, Digi International (Digi). All Rights Reserved. #
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

#############################################################################
#                                                                           #
# Copyright (c) 2006 Pierre Quentel (quentel.pierre@wanadoo.fr)             #
#                                                                           #
# All rights reserved.                                                      #
#                                                                           #
# Redistribution and use in source and binary forms, with or without        # 
# modification, are permitted provided that the following conditions        #
# are met:                                                                  #
#                                                                           #
# 1. Redistributions of source code must retain the above copyright         #
#    notice, this list of conditions and the following disclaimer.          #
# 2. Redistributions in binary form must reproduce the above copyright      #
#    notice, this list of conditions and the following disclaimer in the    #
#    documentation and/or other materials provided with the distribution.   #
# 3. The name of the author may not be used to endorse or promote products  #
#    derived from this software without specific prior written permission.  #
#                                                                           #
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR 'AS IS' AND ANY EXPRESS OR        #
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES #
# OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.   #
# IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT,          #
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT  #
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, #
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY     #
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT       #
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF  #
# THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.         #
#                                                                           #
#############################################################################

"""
"""

import os
import string
import cStringIO
import re
import sys

startIndent=re.compile("<\s*indent\s*>",re.IGNORECASE)
endIndent=re.compile("<\s*/indent\s*>",re.IGNORECASE)

class PIH_ParseError(Exception):

    def __init__(self,value):
	self.msg=value[0]
	self.errorLine=value[1]

    def __str__(self):
	return self.msg

class PIH:

    endTag={"<%":"%>","<%=":"%>","<%_":"%>","<%%":"%%>"}

    def __init__(self,fileName=None):
	self.fileName=fileName
	self.defaultEncoding="yesyes" #k_config.output_encoding
	if fileName:
	    fileObject=open(fileName)
	    self.parse(fileObject)

    def parse(self,fileObject):
	"""Parses the PIH code in the file object open for reading"""
	sourceCode=fileObject.readlines()
	sourceCode=map(self.stripCRLF,sourceCode)
	sourceCode=string.join(sourceCode,'\n')
	self.sourceCode=sourceCode+'\n'
	# normalize <indent> tag
	self.pihCode=startIndent.sub("<indent>",self.sourceCode)
	self.pihCode=endIndent.sub("</indent>",self.pihCode)

	self.pointer=0
	self.indentation="off"
	self.indent=1
	self.defaultIndentation=0
	self.startHTML=self.endHTML=0
	self.sourceLine=0   # current line in source code
	self.lineMapping={} # maps lines in resulting Python code to original line
	self.output=cStringIO.StringIO() # cStringIO because this is a raw python code
					 # we are assembling
	self.output.write("    import sys,string,cStringIO\n") #=cStringIO.StringIO()
	self.output.write("    py_code=cStringIO.StringIO()\n")
	self.destLine=1 # first line with an origin in pih code
	while self.pointer<len(self.pihCode):
	    rest=self.pihCode[self.pointer:]
	    if rest.startswith("<indent>"):
		# start a part where indentation is on
		self.flushHTML()
		self.indentation="on"
		self.defaultIndentation=self.getAbsLineIndent(self.pointer)
		self.pointer=self.pointer+8
		self.startHTML=self.pointer
	    elif rest.startswith("</indent>"):
		# ends a part where indentation is on
		self.flushHTML()
		self.indentation="off"
		self.indent=0
		self.pointer=self.pointer+9
		self.startHTML=self.pointer
	    elif rest.startswith("<%=") or rest.startswith("<%_"):
		# inserting a variable or string to translate
		# translates a variable as sys.stdout.write(variable)
		# and a string to translate as sys.stdout.write(_(translated))
		# a variable can be on several lines
		tag=self.pihCode[self.pointer:self.pointer+3]
		taggedCode,start,end=self.initTag(tag)
		taggedCode=string.strip(taggedCode)
		if self.indentation=="on":
		    self.indent=self.getLineIndent(self.pointer)
		self.output.write(" "*4*self.indent)
		if tag=="<%=":
		    # this will break with non-ascii strings intended
		    # as original phrases for gettext
		    # fortunately, everyone uses English as the original
		    # if not, we'll wait for the bugreports :-/
		    self.output.write('py_code.write(str(')
		else:
		    self.output.write('py_code.write(_(')
		startLineNum=self.getLineNum(start)
		varCodeLines=string.split(taggedCode,"\n")
		for i in range(len(varCodeLines)):
		    line=varCodeLines[i]
		    if not string.strip(line):
			continue
		    line=string.rstrip(line)
		    if i!=0:
			self.output.write(" "*4*self.indent)
		    self.output.write(line)
		    if i !=len(varCodeLines)-1:
			self.output.write("\n")
		    self.lineMapping[self.destLine]=startLineNum+i
		    self.destLine+=1
		self.output.write("))\n")
		self.pointer=end
		self.startHTML=self.pointer
	    elif rest.startswith("<%"):
		# inserting Python statements
		pythonCode,pythonStart,pythonEnd=self.initTag("<%")
		startLineNum=self.getLineNum(pythonStart)
		if string.lower(string.strip(pythonCode))=="end":
		    # if <% end %>, only decrement indentation
		    self.indent-=1
		else:
		    pythonCodeLines=string.split(pythonCode,"\n")
		    for i in range(len(pythonCodeLines)):
			line=pythonCodeLines[i]
			if not string.strip(line):
			    continue
			if i==0:
			    self.indent=self.getLineIndent(self.pointer)
			    if self.indentation=="off":
				self.indent1=self.getAbsLineIndent(self.pointer)
			else:
			    self.indent=self.getIndent(line)
			if self.indentation=="on":
			    line=string.strip(line)
			elif i>0:
			    # if not under <indent>, removes the same heading whitespace
			    # as the first line
			    j=0
			    while line and line[j] in string.whitespace:
				j+=1
			    if j<self.indent1:
				errorLine=startLineNum+i+1
				errMsg="Indentation error :\nline %s"
				errMsg+=" can't be less indented than line %s"
				raise PIH_ParseError, [errMsg \
				    %(errorLine,startLineNum+1),errorLine-1]
			    line=" "*4*(j-self.indent1)+line.strip()
			self.output.write(" "*4*self.indent)
			self.output.write(string.rstrip(line)+"\n")
			self.lineMapping[self.destLine]=startLineNum+i
			self.destLine+=1
		    if self.indentation=="off":
			if line.strip().endswith(":"):
			    self.indent+=1
		self.pointer=pythonEnd
		self.startHTML=self.pointer
	    else:
		self.pointer=self.pointer+1
		self.endHTML=self.pointer

	self.flushHTML()
	if self.defaultEncoding:
	    # now we can guess the encoding of output...
	    val = self.output.getvalue()
	    enc = "yes"	 # k_encoding.guess_buffer_encoding(val, self.defaultEncoding)
	    # this is ugly, but unfortunately exec cannot take unicode strings,
	    # neither can be told about encoding the code is using
	    # so we have to do it this way...
	    self.output=cStringIO.StringIO()
	    #self.output.write("# -*- coding: %s -*-\n" % enc.pyencoding)
	    self.output.write(val)
	    self.lineMapping = dict([(k+1,v)
			    for (k,v) in self.lineMapping.iteritems()])

    def stripCRLF(self,line):
	while line and line[-1] in ['\r','\n']:
	    line=line[:-1]
	return line

    def initTag(self,tag):
	"""Search the closing tag matching **tag**, move pointer
	and flush current HTML
	"""
	tagEnd=string.find(self.pihCode,self.endTag[tag],self.pointer)
	if tagEnd<0:
	    errorLine=self.getLineNum(self.pointer)+1
	    raise PIH_ParseError, \
		["unclosed %s tag in line %s" %(tag,errorLine),errorLine]
	# flushes existing html
	self.flushHTML()
	start=self.pointer+len(tag)
	while self.pihCode[start] in string.whitespace:
	    start=start+1
	code=self.pihCode[start:tagEnd]
	end=tagEnd+len(self.endTag[tag])
	return code,start,end

    def flushHTML(self):
	"""Flush aggregated HTML"""
	html=self.pihCode[self.startHTML:self.endHTML]
	if html:
	    htmlLines=string.split(html,"\n")
	    p=self.startHTML
	    for i,htmlLine in enumerate(htmlLines):
		if htmlLine:
		    if self.indentation=="on":
			self.indent=self.getLineIndent(p)
		    out=htmlLine
		    #if i>0:
		    #	out=string.lstrip(htmlLine) # strips indentation
		    out=string.replace(out,"\\",r"\\")
		    out=string.replace(out,"'",r"\'")
		    out=string.replace(out,'"',r'\"')
		    if out:
			if i==len(htmlLines)-1 and not out.strip():
			    # if last HTML chunk is whitespace, ignore
			    # (must be the indentation of next Python chunk)
			    break
			if i!=len(htmlLines)-1:
			    out=out+'\\n'
			self.output.write(" "*4*self.indent)
			self.output.write('py_code.write("%s")\n' %out)
			self.lineMapping[self.destLine]=self.getLineNum(p)
			self.destLine+=1
		p=p+len(htmlLine)+1

    def getLineNum(self,pointer):
	return string.count(self.pihCode,"\n",0,pointer)

    def nextNoSpace(self,p):
	while p<len(self.pihCode) and self.pihCode[p] in [' ','\t']:
	    p=p+1
	return p

    def countLeadingTabs(self,line):
	res=0
	while res<len(line) and line[res] in ["\t"," "]:
	    res+=1
	return res

    def getIndent(self,line):
	if self.indentation=="off":
	    return self.indent
	else:
	    i=0
	    while i<len(line) and line[i] in string.whitespace:
		i=i+1
	    return i-self.defaultIndentation

    def getAbsLineIndent(self,pointer):
	"""Get the absolute indentation of the line where **pointer** is"""
	p=pointer
	while p>0 and self.pihCode[p]!="\n":
	    p=p-1
	p=p+1
	indent=0
	while p<len(self.pihCode) and self.pihCode[p] in string.whitespace:
	    p+=1
	    indent+=1
	return indent

    def getLineIndent(self,pointer):
	"""Returns indentation of the line which includes the position
	**pointer** in self.pihCode
	If we're under <indent>, indentation is relative to
	self.defaultIndentation"""
	if self.indentation=="on":
	    self.indent=self.getAbsLineIndent(pointer)-self.defaultIndentation
	return self.indent

    def pythonCode(self):
	"""Returns Python code as a string"""
	return self.output.getvalue()

    def getLineMapping(self):
	return self.lineMapping

    def trace(self,data):
	sys.stderr.write("%s\n" %data)

#
# Use PythonInsideHTML above to compile everything into a pyhtml.py
#

def compile_pyhtmls( inp ="src/presentations/embedded_web", outp="src/presentations/embedded_web/pyhtml.py" ):
  """
  locates all files in a given directory (given by "inp" kwarg) with a .pyhtml and use the
  PythonInsideHTML functions to generate python code that will reside inside the output file
  given by the "outp" kwarg.  The code for each pyhtml file will be within a function called
  the name of the file, it will return a cStringIO object that contains the HTML output.
  """
  out = open(outp,"w")
  for root, dirs, files in os.walk(inp):
	for f in files:
		if f.endswith(".pyhtml"):
			out.write("def %s(request):\n    \"\"\"auto-generated from %s\"\"\"\n"%(os.path.basename(f).split(".")[0],f))
			p = PIH(inp+"/"+f)
			data = p.pythonCode()
			out.write(data)
			out.write("    return py_code\n\n")
if __name__=="__main__":
    compile_pyhtmls()

