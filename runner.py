#import steam.guard,time
import time
#from base64 import b64decode
import base64
#import steam.webauth as wa
import os,re,json,requests,sys,getopt
from bs4 import BeautifulSoup
#from steam.client import SteamClient
from steampy import guard
import rsa

#来自：https://github.com/ZangYUzhang/Steam_login
class LoginExecutor:
    def __init__(self, username: str, password: str, shared_secret: str, session: requests.Session = requests.Session()) -> None:
        self.username = username
        self.password = password
        self.shared_secret = shared_secret
        self.session = session
        self.client_id = ''
        self.steamid = ''
        self.request_id = ''
        self.refresh_token = ''

    def login(self) -> requests.Session:
        login_response = self._send_login_request()  # 创建登录会话
        self._update_stem_guard(login_response)
        self._pool_sessions_steam()
        finallized_response = self._finallez_login()
        self._set_tokens(finallized_response)
        self.set_sessionid_cookies()

        return self.session

    def _send_login_request(self) -> requests.Response:
        rsa_params = self._fetch_rsa_params()
        data = {
            'persistence': "1",
            'encrypted_password': rsa_params['encrypted_password'],
            'account_name': self.username,
            'encryption_timestamp': rsa_params['rsa_timestamp'],
        }
        response = self.session.post("https://api.steampowered.com/IAuthenticationService/BeginAuthSessionViaCredentials/v1", data=data)
        return response

    def set_sessionid_cookies(self):
        sessionid = self.session.cookies.get_dict().get('sessionid')

        community_cookie = {"name": "sessionid",
                            "value": sessionid,
                            "domain": 'steamcommunity.com'}
        self.session.cookies.set(**community_cookie)

        store_cookie = {"name": "sessionid",
                        "value": sessionid,
                        "domain": 'store.steampowered.com'}
        self.session.cookies.set(**store_cookie)

    def _fetch_rsa_params(self, retry: int = 3) -> dict:
        self.session.post("https://steamcommunity.com")  # 获得第一个Cookies
        response = self.session.get("https://api.steampowered.com/IAuthenticationService/GetPasswordRSAPublicKey/v1/?account_name=" + self.username)
        key_response = json.loads(response.text)
        for i in range(retry):
            try:
                rsa_mod = int(key_response["response"]['publickey_mod'], 16)
                rsa_exp = int(key_response["response"]['publickey_exp'], 16)
                rsa_timestamp = key_response["response"]['timestamp']
                rsa_key = rsa.PublicKey(rsa_mod, rsa_exp)
                encrypted_password = base64.b64encode(rsa.encrypt(self.password.encode('utf-8'), rsa_key))
                return {'encrypted_password': encrypted_password,
                        'rsa_timestamp': rsa_timestamp}
            except KeyError:
                if retry >= 2:
                    raise ValueError('Could not obtain rsa-key')

    def _update_stem_guard(self, login_response):
        response_json = json.loads(login_response.text).get('response')
        self.client_id = response_json.get('client_id')
        self.steamid = response_json.get('steamid')
        self.request_id = response_json.get('request_id')
        code = guard.generate_one_time_code(self.shared_secret)

        update_data = {
            'client_id': self.client_id,
            'steamid': self.steamid,
            'code_type': 3,
            'code': code
        }

        response = self.session.post("https://api.steampowered.com/IAuthenticationService/UpdateAuthSessionWithSteamGuardCode/v1/", data=update_data)

    def _pool_sessions_steam(self):
        pool_data = {
            'client_id': self.client_id,
            'request_id': self.request_id
        }
        response = self.session.post("https://api.steampowered.com//IAuthenticationService/PollAuthSessionStatus/v1/", data=pool_data)
        response_json = json.loads(response.text)
        self.refresh_token = response_json.get("response").get("refresh_token")

    def _finallez_login(self) -> requests.Response:
        try:
            sessionid = self.session.cookies.get_dict().get('sessionid')
        except Exception:
            print("获取sessionid失败", self.session.cookies.get_dict())
            raise Exception("Steam_login.py , 获取sessionid失败")
        else:
            redir = "https://steamcommunity.com/login/home/?goto="

            finallez_data = {
                'nonce': self.refresh_token,
                'sessionid': sessionid,
                'redir': redir
            }

            response = self.session.post("https://login.steampowered.com/jwt/finalizelogin", data=finallez_data)
            return response

    def _set_tokens(self, fin_resp: requests.Response):
        response_json = json.loads(fin_resp.text)
        transfer_info = response_json.get("transfer_info")
        for item in transfer_info[:2]:
            params = item.get('params')
            data = {
                'nonce': params.get("nonce"),
                'auth': params.get("auth"),
                'steamID': self.steamid
            }
            response = self.session.post(item.get('url'), data=data)

    def test_is_logined(self):
        resp = self.session.get(f"https://steamcommunity.com/profiles/{self.steamid}/home")
        print(resp.text)

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
#    argv=getArgv()
#    user = wa.WebAuth(argv['userName'])
#    try:
#        user.login(argv['passWord'])
#    except wa.TwoFactorCodeRequired:
#        t = time.time()
#        user.login(twofactor_code=steam.guard.generate_twofactor_code_for_time(b64decode(argv['sharedSecret']),int(t)))
#    return user
    login = LoginExecutor('Left024', 'p2$$@D%4id3x22Jg', 't/jkCpmJYOQRD3WsBZWKYv34ytU=')
    session = login.login()
    return session

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
#t = time.time()
#client.login(two_factor_code=steam.guard.generate_twofactor_code_for_time(b64decode(argv['sharedSecret']),int(t)), username=argv['userName'], password=argv['passWord'])

needDownload=False
for id in ownedGames['response']['games']:
    rtime_last_played={}
    try:
        if id['rtime_last_played']>lastPlayed[str(id['appid'])]['rtime_last_played'] and id['rtime_last_played'] != 0 and id['appid']!=313340:         
            #client.idle()
            if not needDownload:
                needDownload=True
                session=steamLogin()
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
            downloadSteamGamesSavesWithGameID(session,str(id['appid']),str(id['name']))
            rtime_last_played['name']=id['name']
            rtime_last_played['rtime_last_played']=id['rtime_last_played']
            lastPlayed[str(id['appid'])]=rtime_last_played
        
write_json_data(lastPlayed,"lastPlayed.json")
