import steam.guard,time
#import time
from base64 import b64decode
#import base64
import steam.webauth as wa
import os,re,json,requests,sys,getopt
from bs4 import BeautifulSoup
from steam.client import SteamClient

def get_json_data(json_path):
    try:
        with open(json_path,'rb') as f:
            params = json.load(f)
        f.close()
    except FileNotFoundError:
        os.mknod(json_path)
        params={}
    except ValueError:
        params={}
    return params

def write_json_data(dict,path):
    with open(path,'w') as r:
        json.dump(dict,r,indent=4,ensure_ascii=False)
    r.close()

def getArgv():
    list={}
    argv = sys.argv[1:]
    try:
        opts,args = getopt.getopt(argv, "u:p:s:a:i:",["userName=","passWord=","sharedSecret=","apiKey=","steamID="])
    except:
        print("Error")
        return list
    for opt,arg in opts:
        if opt in ['-u', '--userName']:
            list['userName']=arg
        elif opt in ['-p', '--passWord']:
            list['passWord']=arg
        elif opt in ['-s', '--sharedSecret']:
            list['sharedSecret']=arg
        elif opt in ['-a', '--apiKey']:
            list['apiKey']=arg
        elif opt in ['-i', '--steamID']:
            list['steamID']=arg
    return list

def steamLogin():
    argv=getArgv()
    user = wa.WebAuth()
    try:
        t = time.time()
        user.login(username='Left024',password=argv['passWord'],code=steam.guard.generate_twofactor_code_for_time(b64decode(argv['sharedSecret']),int(t)))
    except wa.TwoFactorCodeRequired:
        t = time.time()
        user.login(code=steam.guard.generate_twofactor_code_for_time(b64decode(argv['sharedSecret']),int(t)))
    return user.session

def getSteamOwnedGames():
    argv=getArgv()
    try:
        return json.loads(requests.get('https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?key='+argv['apiKey']+'&steamid='+argv['steamID']+'&include_appinfo=true&format=json').text)
    except:
        print('getSteamOwnedGames except')
        return {}

def downloadSteamGamesSavesWithGameID(session,id,gameName):
    print("Downloading "+gameName+" saves")
    gameSavesCache=get_json_data("gameSavesCache.json")
    hasNextPage=True
    index=0
    url="https://store.steampowered.com/account/remotestorageapp/?appid="+str(id)
    while hasNextPage:
        fileNameJson={}
        #session=user.session.get(url)
        res=session.get(url)
        soup = BeautifulSoup(res.text, 'html5lib')
        for idx, tr in enumerate(soup.find_all('tr')):
            fileNameDetailJson={}
            if idx != 0:
                tds = tr.find_all('td')
                fileName=tds[1].contents[0][1:-1]
                try:
                    if gameSavesCache[str(id)][fileName]['size']!=tds[2].contents[0][1:-1] and gameSavesCache[str(id)][fileName]['time']!=tds[3].contents[0][1:]:
                        if fileName.rfind("/")!=-1:
                            if not os.path.exists("SteamSaves/"+gameName+"/"+fileName[:fileName.rfind("/")]):
                                os.makedirs("SteamSaves/"+gameName+"/"+fileName[:fileName.rfind("/")])
                        else:
                            if not os.path.exists("SteamSaves/"+gameName):
                                os.makedirs("SteamSaves/"+gameName)
                        attempts = 0
                        success = False
                        while attempts < 6 and not success:
                            try:
                                data = requests.get(re.search('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', str(tds[4])).group())
                                with open("SteamSaves/"+gameName+"/"+tds[1].contents[0][1:-1], 'wb')as file:
                                    file.write(data.content)
                                success=True
                            except Exception as e:
                                print(e)
                                attempts += 1
                                if attempts == 5:
                                    break
                                else:
                                    time.sleep(10)
                                    print("Retry download "+fileName+" ("+attempts+")")
                                #pass
                                #continue
                        fileNameDetailJson['size']=tds[2].contents[0][1:-1]
                        fileNameDetailJson['time']=tds[3].contents[0][1:]
                        fileNameJson[fileName]=fileNameDetailJson
                        gameSavesCache[str(id)]=fileNameJson
                    else:
                        print("Skip "+fileName)
                except:
                    print("except")
                    if fileName.rfind("/")!=-1:
                        if not os.path.exists("SteamSaves/"+gameName+"/"+fileName[:fileName.rfind("/")]):
                            os.makedirs("SteamSaves/"+gameName+"/"+fileName[:fileName.rfind("/")])
                    else:
                        if not os.path.exists("SteamSaves/"+gameName):
                            os.makedirs("SteamSaves/"+gameName)
                    attempts = 0
                    success = False
                    while attempts < 6 and not success:
                        try:
                            data = requests.get(re.search('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', str(tds[4])).group())
                            with open("SteamSaves/"+gameName+"/"+tds[1].contents[0][1:-1], 'wb')as file:
                                file.write(data.content)
                            success=True
                        except Exception as e:
                            print(e)
                            attempts += 1
                            if attempts == 5:
                                break
                            else:
                                time.sleep(10)
                                print("Retry download "+fileName+" ("+attempts+")")
                    fileNameDetailJson['size']=tds[2].contents[0][1:-1]
                    fileNameDetailJson['time']=tds[3].contents[0][1:]
                    fileNameJson[fileName]=fileNameDetailJson
                    gameSavesCache[str(id)]=fileNameJson
        matchNextPage=re.findall('https://store.steampowered.com/account/remotestorageapp\?appid='+id+'&index=\d+',res.text)
        if len(matchNextPage)>0:
            for x in range(len(matchNextPage)):
                if int(matchNextPage[x][len("https://store.steampowered.com/account/remotestorageapp?appid="+id+"&index="):])>index:
                    hasNextPage=True
                    url=matchNextPage[x]
                    index=int(matchNextPage[x][len("https://store.steampowered.com/account/remotestorageapp?appid="+id+"&index="):])
                else:
                    hasNextPage=False
        else:
            break
    write_json_data(gameSavesCache, "gameSavesCache.json")

lastPlayed=get_json_data("lastPlayed.json")
ownedGames=getSteamOwnedGames()

#client = SteamClient()
argv=getArgv()

#user=steamLogin()
#url="https://store.steampowered.com/account/remotestorageapp/?appid=313340"
#res=user.session.get(url)
#print(res.text)
BlackList=[313340,578080]
needDownload=False
if 'response' in ownedGames:
    for id in ownedGames['response']['games']:
        rtime_last_played={}
        print("Strat "+id['name'])
        try:
            if id['rtime_last_played']>lastPlayed[str(id['appid'])]['rtime_last_played'] and id['rtime_last_played'] != 0 and id['appid'] not in BlackList:         
                #client.idle()
                if not needDownload:
                    needDownload=True
                    session=steamLogin()
                    #client.idle()
                    #session=client.get_web_session()
                downloadSteamGamesSavesWithGameID(session,str(id['appid']),str(id['name']))
                rtime_last_played['name']=id['name']
                rtime_last_played['rtime_last_played']=id['rtime_last_played']
                lastPlayed[str(id['appid'])]=rtime_last_played
            else:
                print("Skip "+id['name'])
        except:
            if id['appid']!=313340:
                #client.idle()
                if not needDownload:
                    needDownload=True
                    session=steamLogin()
                    #client.idle()
                    #session=client.get_web_session()
                downloadSteamGamesSavesWithGameID(session,str(id['appid']),str(id['name']))
                rtime_last_played['name']=id['name']
                rtime_last_played['rtime_last_played']=id['rtime_last_played']
                lastPlayed[str(id['appid'])]=rtime_last_played
            
    write_json_data(lastPlayed,"lastPlayed.json")
