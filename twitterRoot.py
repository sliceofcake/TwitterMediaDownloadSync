# coding=utf-8
import threading
import urllib
import urllib2
import re
import os
import glob
import sys
import getopt
import math
import time
import Queue

# !!! TODO
# • is {"Connection":"keep-alive"} being properly used? is it needed? is it helping? is it hurting?

#escape a filename [sounds bad, but I really don't have a guarantee that this is enough]
def esc(m):
	s = str(m)
	# dots are only useful for path traversal if nearby slashes, which we get rid of, so they should only be dangerous by themselves
	if s == "." :return "。"
	if s == "..":return "。。"
	s = re.sub('\\\\','＼',s)
	s = re.sub('/','／',s)
	s = re.sub('"','”',s)
	s = re.sub('\'','’',s)
	s = re.sub('\*','＊',s)
	s = re.sub('\$','＄',s)
	s = re.sub(':','：',s) # Apple's handling of this being a special character
	return s
# if folder exists, good. if not, and no similars, make it. if not and similar[s], take first similar and rename it.
def assertFolder(foldername=None,wildname=None):
	if not os.path.isdir(foldername):
		if wildname is None:
			os.mkdir(foldername)
		else:
			matchA = glob.glob(wildname)
			if len(matchA) == 0:
				os.mkdir(foldername)
			else:
				os.rename(matchA[0],foldername)
def printUsage():
	global p
	sys.stdout.write("usage   : python twitterRoot.py [-t threadcount] [--complete]"+os.linesep)
	sys.stdout.write("example : python twitterRoot.py"+os.linesep)
	sys.stdout.write("example : python twitterRoot.py --complete"+os.linesep)
	sys.stdout.write("example : python twitterRoot.py -t 32 --complete"+os.linesep)
	sys.stdout.write("-h                : display help information, which is what you're reading right now"+os.linesep)
	sys.stdout.write("--help            : display help information, which is what you're reading right now"+os.linesep)
	sys.stdout.write("--complete        : will scan over all images, even after it recognizes some of them"+os.linesep)
	sys.stdout.write("                    usually, the scanner will stop as soon as it sees a familiar image"+os.linesep)
	sys.stdout.write("                    this option is intended for rarely-done checks of completeness"+os.linesep)
	sys.stdout.write("-t threadcount    : number of threads used"+os.linesep)
	sys.stdout.write("                    type : integer | minimum : 1 | maximum : "+str(p["threadMaxC"])+" | default : "+str(p["threadC"])+os.linesep)
	sys.stdout.write("                    as you use more threads, your download rate and CPU usage will rise"+os.linesep)
	sys.stdout.write("                    out of courtesy toward pixiv, I recommend keeping threadcount relatively low"+os.linesep)
	sys.stdout.flush()
def ll(m,colorS="default",noLineBreakF=False):
	global p
	sys.stdout.write(("" if colorS=="default" else p["cliColorO"][colorS])+str(m)+("" if colorS=="default" else p["cliColorO"]["end"])+("" if noLineBreakF else os.linesep))
	sys.stdout.flush()
def fail(m):
	global p
	ll(m,"r")
	sys.exit()
# warning : not diamond-solid
def readFile(filenameS):
	# os.path.isfile(filenameS)
	try:
		file = open(filenameS,"r")
	except EOError as err:
		return None
	txt = file.read()
	file.close()
	return txt
# warning : not diamond-solid
def assertFile(filenameS):
	if not os.path.isfile(filenameS):
		file = open(filenameS,"w")
		file.write("")
		file.close()
def extractLinkData(linkS,method="GET",dataO={},headerO={},returnFalseOnFailureF=False):
	req = urllib2.Request(linkS,urllib.urlencode(dataO),headerO)
	req.get_method = lambda : method
	try:response = urllib2.urlopen(req)
	except urllib2.HTTPError as err:
		if returnFalseOnFailureF:return False
		else:fail(linkS+" : "+str(err))
	res = {"txt":response.read(),"txtHeader":str(response.info()),}
	response.close()
	return res
p = {
	"threadC"          : 16,
	"threadMaxC"       : 64,
	"stopOnFoundF"     : True,
	"userIDA"          : [],
	"jobEQueue_stage1" : Queue.Queue(),
	"jobEQueue_stage2" : Queue.Queue(),}
# command-line interface colors, enabled for mac os x where I know it works, disabled everywhere else
# https://docs.python.org/2/library/sys.html#platform
# System              | platform value
# --------------------+---------------
# Linux (2.x and 3.x) | 'linux2'
# Windows             | 'win32'
# Windows/Cygwin      | 'cygwin'
# Mac OS X            | 'darwin'
# OS/2                | 'os2'
# OS/2 EMX            | 'os2emx'
# RiscOS              | 'riscos'
# AtheOS              | 'atheos'
if sys.platform == "darwin":
	p["cliColorO"] = {
		"r"         : "\033[91m",
		"g"         : "\033[92m",
		"b"         : "\033[94m",
		"c"         : "\033[96m",
		"m"         : "\033[95m",
		"y"         : "\033[93m",
		"gray"      : "\033[90m",
		"end"       : "\033[0m",
		# plain color [colored BIU exists, look it up if you want it]
		"bold"      : "\033[1m",
		"underline" : "\033[4m",}
else:
	p["cliColorO"] = {
		"r"         : "",
		"g"         : "",
		"b"         : "",
		"c"         : "",
		"m"         : "",
		"y"         : "",
		"gray"      : "",
		"end"       : "",
		# plain color [colored BIU exists, look it up if you want it]
		"bold"      : "",
		"underline" : "",}



ll("---- START ----","c")
ll("To stop this program, use Control+Z for Apple Operating Systems.","m")




# handle command-line arguments
# ----------------------------------------------------------------------------------------------------------------------
try:optA,leftoverA = getopt.getopt(sys.argv[1:],'ht:T:',['help','complete'])
except getopt.GetoptError as err:printUsage();fail("ERROR : "+str(err))
for opt,arg in optA:
	if opt in ["-h","--help"]:printUsage();sys.exit()
	if opt in ["--complete"]:p["stopOnFoundF"] = False
	if opt in ["-t"]:
		try:p["threadC"] = int(arg)
		except ValueError as err:fail("ERROR : [-t threadcount] argument not integer : "+arg)
		if p["threadC"] <               1:fail("ERROR : [-t threadcount] argument too small (min:1) : "+arg)
		if p["threadC"] > p["threadMaxC"]:fail("ERROR : [-t threadcount] argument too large (max:"+str(p["threadMaxC"])+") : "+arg)




# handle userIDA.txt
# ----------------------------------------------------------------------------------------------------------------------
assertFile("userIDA.txt")
txt = readFile("userIDA.txt")
# remove comments
txt = re.sub(re.compile('//.*$',re.MULTILINE),'',txt)
# remove @ symbol
txt = re.sub(re.compile('@'),'',txt)
# parse for IDs
userIDSA = re.split('\\s+',txt)
for userIDS in userIDSA:
	if userIDS != "": # because of how the regex split that I wrote works, blanks may show up at the front and back
		p["userIDA"].append(userIDS)
		p["jobEQueue_stage1"].put({"classnameS":"Stage1Job","argO":{"userIDS":userIDS}},False)
if len(p["userIDA"]) == 0:fail("ERROR : Fill in your userIDA.txt file with pixiv userIDs (the number found in the URL bar for a profile page), one per line")
ll("userID List : "+str(p["userIDA"]))




# handle latest.txt
# ----------------------------------------------------------------------------------------------------------------------
#assertFile("latest.txt")
#txt = readFile("latest.txt")
#lineSA = re.split('\\r?\\n',txt)
#for lineS in lineSA:
#	componentSA = re.split('\\s+',lineS)
#	if len(componentSA) != 2:
#		continue
#	ll(componentSA[0] + "..." + componentSA[1])
#sys.exit()
#




# scan each artist for image download links
# ----------------------------------------------------------------------------------------------------------------------
class Stage1Job():
	def __init__(self,userIDS=""):
		self.userIDS = userIDS
	def run(self):
		global p
		userIDS = self.userIDS
		imageEA = []
		try: # try-except-finally misused here so that "return" takes it to the finally block, where we can wrap up
			posMaxS = ""
			while True:
				# make the page request
				#ll("https://twitter.com/i/profiles/show/"+userIDS+"/media_timeline"+("" if posMaxS == "" else "?max_position="+posMaxS))
				reqE = extractLinkData("https://twitter.com/i/profiles/show/"+userIDS+"/media_timeline"+("" if posMaxS == "" else "?max_position="+posMaxS),"GET",{},{"Connection":"keep-alive",})
				
				assertFolder(foldername=userIDS)
				
				m = re.findall('data\-image\-url=\\\\"https:\\\\/\\\\/pbs\.twimg\.com\\\\/media\\\\/(.+?\.[a-zA-Z0-9\-_]+)\\\\"',reqE["txt"])
				
				# if we have image matches
				if len(m) == 0:
					return
				
				for filename in m:
					foundO = {
						"pathLocal"  : userIDS+"/"+esc(filename),
						# !!! write to be generic to any found link (de-JSON-ify the string and use it)
						"url"        : "https://pbs.twimg.com/media/" + filename + ":orig",
						"pathLatest" : userIDS+"/"+"latest.txt",
						"filename"   : filename,}
					fileFoundLocalF = os.path.isfile(foundO["pathLocal"])
					
					# stopOnFoundF stop condition
					if fileFoundLocalF and p["stopOnFoundF"]:
						ll(        userIDS      .rjust(18," ")+" userID"
							+" | "+("✕ download?" if fileFoundLocalF else "◯ download?")+""
							+" | "+foundO["pathLocal"].ljust(17," ")+""
							,("default" if fileFoundLocalF else "g"))
						# the finally block will take up our work after this point [not an actual return, just a break-all construct]
						return
					
					ll(        userIDS      .rjust(18," ")+" userID"
						+" | "+("✕ download?" if fileFoundLocalF else "◯ download?")+""
						+" | "+foundO["pathLocal"].ljust(17," ")+""
						+" | "+foundO["url"]
						,("default" if fileFoundLocalF else "g"))
					
					if not fileFoundLocalF:
						imageEA.append({"url":foundO["url"],"pathLocal":foundO["pathLocal"],"pathLatest":foundO["pathLatest"],"filename":foundO["filename"]})
				
				m = re.findall('data-tweet-id=\\\\"(\d+)\\\\"',reqE["txt"])
				if len(m) == 0:
					return
				
				for posS in m:
					posMaxS = posS
				
		finally:
			if len(imageEA) >= 1:
				imageEQueue = Queue.Queue()
				for imageE in reversed(imageEA):
					imageEQueue.put(imageE)
				p["jobEQueue_stage2"].put({"classnameS":"Stage2Job","argO":{"imageEQueue":imageEQueue}})

class Stage2Job():
	def __init__(self,imageEQueue):
		self.imageEQueue = imageEQueue
	def run(self):
		while True:
			try:
				imageE = self.imageEQueue.get(False)
			except Queue.Empty:
				return
			#ll("△ "+imageE["pathLocal"],"gray")
			reqE = extractLinkData(imageE["url"],"GET",{},{"Connection":"keep-alive",})
			text_file = open(imageE["pathLocal"],"w")
			text_file.write(reqE["txt"])
			text_file.close()
			
			#assertFile(imageE["pathLatest"])
			#text_file = open(imageE["pathLatest"],"w")
			#text_file.write(imageE["filename"])
			#text_file.close()
			
			ll("◯ "+imageE["pathLocal"],"g")

class Proc(threading.Thread):
	def __init__(self,getFxn):
		super(Proc,self).__init__()
		self.getFxn = getFxn
	def run(self):
		global p
		while True:
			jobE = self.getFxn()
			if jobE == None:
				return
			job = globals()[jobE["classnameS"]](**jobE["argO"])
			job.run()




# scan for each image
# ----------------------------------------------------------------------------------------------------------------------
# multithreaded execute
tA = []
def stage1Fxn():
	global p
	try:
		return p["jobEQueue_stage1"].get(False)
	except Queue.Empty:
		return None
for i in xrange(p["threadC"]):
	t = Proc(getFxn=stage1Fxn)
	t.daemon = True
	tA.append(t)
	t.start()
for t in tA:
	t.join()
tA = []

# read through the queue (without, in the end, modifying it) to count the number of images to download
tempQueue = Queue.Queue()
imageN = 0
while True:
	try:
		jobE = p["jobEQueue_stage2"].get(False)
	except Queue.Empty:
		break
	imageN += jobE["argO"]["imageEQueue"].qsize()
	tempQueue.put(jobE)
while True:
	try:
		jobE = tempQueue.get(False)
	except Queue.Empty:
		break
	p["jobEQueue_stage2"].put(jobE)




# download each image
# ----------------------------------------------------------------------------------------------------------------------
# multithreaded execute
# go in reverse, if the script gets interrupted, then when it's next executed, it won't [as-often] improperly trigger the stopOnFoundF flag
ll("Downloading "+str(imageN)+" images...","m")
tA = []
def stage2Fxn():
	global p
	try:
		return p["jobEQueue_stage2"].get(False)
	except Queue.Empty:
		return None
for i in xrange(p["threadC"]):
	t = Proc(getFxn=stage2Fxn)
	t.daemon = True
	tA.append(t)
	t.start()
for t in tA:
	t.join()
tA = []


ll(os.linesep+"END","c")
