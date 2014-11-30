def stamp():
    return now('%Y%m%d%H%M%S') + '%03d' % random.randint(0, 1000)


def stamp2():
    return int((time.time() / 1000) % 1 * 1000000)


def get_ret(cdata):
    io = StringIO.StringIO(cdata)
    z = gzip.GzipFile(fileobj=io, mode='rb')
    return json.loads(z.read())


class Client(object):
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.uid = None
        self.token = None
        self.api_token = None
        self.xid = 0
        self.idfa = uuid_str()
        self.idfv = uuid_str()

    def login(self):
        ok, _ = self.kongzhong_login()
        if ok:
            ok, _ = self.paycenter_login()
        return ok, _

    def kongzhong_login(self):
        headers = {'Accept-Encoding': 'gzip', 'User-Agent': '我家女儿真可爱 3.0.2 (iPhone; iPhone OS 8.1.1; en_US)'}

        key = base64.b64decode('82HTu6Az2lilodn16Gx2532ABVrEezen42NUVo3J3+E=')

        data = {"DeviceID": self.idfa, "stamp": stamp(), "GameID": "4400000", "Method": "PreValidAccount"}
        data = urllib2.quote(aes_encrypt_no_iv(json.dumps(data, separators=(',', ':')), key=key, b64=True))

        ret = http_request_proxy(GET, headers=headers, url='http://api2.kongzhong.com/sdk/ios?data=%s' % data)
        if ret['status'] == 200:
            data = unpad(aes_decrypt_no_iv(ret['html'], key=key, b64=True), 32)
            ok, data = safe_json(data)
            if ok:
                session = data['Session']
            else:
                return False, None
        else:
            return False, ret['status']

        data = {"GameID": "4400000", "stamp": stamp(), "AccountID": self.username, "AccountType": "1", "Method": "ValidAccount", "PwdType": "1", "AccountPwd": self.password, "DeviceID": self.idfa, "Session": session}
        data = urllib2.quote(aes_encrypt_no_iv(json.dumps(data, separators=(',', ':')), key=key, b64=True))
        ret = http_request_proxy(GET, headers=headers, url='http://api2.kongzhong.com/sdk/ios?data=%s' % data)
        if ret['status'] == 200:
            data = unpad(aes_decrypt_no_iv(ret['html'], key=key, b64=True), 32)
            ok, data = safe_json(data)
            if ok:
                self.token = data['Token']
            else:
                return False, None
        else:
            return False, ret['status']
        return True, self.token

    def paycenter_login(self):
        data = {"data": self.token, "pid": "15100A000000000000", "appVer": "3.0.2"}

        headers = {'User-Agent': 'wjgzzka/3.0.2 CFNetwork/711.1.12 Darwin/14.0.0', 'Accept-Language': 'zh-cn', 'Content-Type': 'application/json'}
        ret = http_request_proxy(POST, headers=headers, url='http://xqw.s.i1.ko.cn:8080/pay-center/login', data=json.dumps(data, separators=(',', ':')))
        if ret['status'] == 200:
            userData = get_ret(ret['html'])
            self.uid = userData['gUserId']
            self.api_token = userData['apiToken']
            return True, userData
        return False, http.status

    def api(self, path, exdata={}):
        headers = {'User-Agent': 'iPhone7,2|iPhone OS 8.1.1|wifi||%s|%s' % (self.idfa, self.idfv), 'Content-Type': 'application/json'}
        headers['syhw_xqw_s_token'] = self.api_token
        headers['game_user_id'] = self.uid
        data = {
            "appVer": "3.0.2",
            "deviceType": "IOS",
            "appRoot": False,
            "token": "xqw.s.i1.ko.cn:8080/%s_0_%s_%06d_%d" % (path, self.api_token, stamp2(), self.xid),
            "userId": 0,
            "retry": 0,
            "apiTryTime": '%s.%03d' % (now(), random.randint(0, 1000))
        }
        data.update(exdata)
        ret = http_request_proxy(POST, headers=headers, url='http://xqw.s.i1.ko.cn:8080/%s' % path, data=json.dumps(data, separators=(',', ':')))
        if ret['status'] == 200:
            self.xid += 1
            data = get_ret(ret['html'])
            #print(json.dumps(data, indent=4))
            return True, data
        return False, None

    def user_load(self):
        return self.api('user/load/')

    def quest_start(self, areaId, stageId, guess):
        data = {
            'guestOpenId': guess['openId'],
            'guestHimeId': guess['himeId'],
            'indexNumber': guess['index'],
            'areaId': areaId,
            'stageId': stageId,
            'activeDeckId': 1
        }
        return self.api('quest/start', data)

    def quest_end(self, quest):
        battles = []
        log = {
            'talks': None,
            'battleSerialNo': len(quest['battle']) + (1 if (quest.get('guerrillaBattle') and quest['guerrillaBattle']['encountBossFlg'] is True) else 0),
            'battles': battles,
            'turn': 0,
            'maxCombo': 0,
            'perfect': len(quest['battle']),
            'perfectCombo': 0,
            'great': 0,
            'allAttackComboCount': len(quest['battle']),
        }
        reward = {
            'exp': 0,
            'gameMoney': 0,
            'resultGetTowerScore': 0,
            'resultGetTowerItem': 0,
            'getItem': [
            ]
        }

        data = {
            'questResult': 'GAME_CLEAR',
            'areaId': quest['areaId'],
            'stageId': quest['stageId'],
            'questKey': quest['questKey'],
            'log': log,
            'reward': reward,
        }

        def resolve_battle(no, battle):
            exp = 0
            money = 0
            bossFlag = False

            for obj in battle['battleObject']:
                exp += obj['exp']
                money += obj['gameMoney']

                if obj.get('treasure') is not None and obj['treasure']['itemType'] == 'HIME':
                    reward['getItem'].append({
                        "itemType": obj['treasure']['itemType'],
                        "value": obj['treasure']['value'],
                        "visual": obj['treasure']['visual'],
                        "key": obj['treasure']['key'],
                        "battleNo": no,
                        "id": obj['treasure']['id'],
                    })

                if obj.get('treasure') is not None and obj['treasure']['itemType'] == 'GAME_MONEY':
                    money += obj['treasure']['value']

            if battle.get('boss') is not None:
                boss = battle['boss']
                bossFlag = True
                money += boss['gameMoney']
                exp += boss['exp']
                if boss.get('treasure') is not None and boss['treasure']['itemType'] == 'HIME':
                    reward['getItem'].append({
                        "itemType": boss['treasure']['itemType'],
                        "value": boss['treasure']['value'],
                        "visual": boss['treasure']['visual'],
                        "key": boss['treasure']['key'],
                        "battleNo": no,
                        "id": boss['treasure']['id'],
                    })

            money += battle['perfectGameMoney']

            reward['exp'] += exp
            reward['gameMoney'] += money

            item = {
                "turn": 0,
                "attack": 0,
                "continueCt": 0,
                "skillCt": 1,
                "maxCombo": 0,
                "exp": exp,
                "gameMoney": money,
                "guerrillaFlg": False,
                "id": battle['id'],
                "battleType": battle['battleType'],
                "resultType": "PERFECT",
                "battleNo": no,
                "bossFlg": bossFlag,
                "perfectFlg": True,
                "greatFlg": False
            }
            return item

        for no, battle in zip(range(len(quest['battle'])), quest['battle']):
            battles.append(resolve_battle(no, battle))

        if quest.get('guerrillaBattle') and quest['guerrillaBattle']['encountBossFlg'] is True:
            no_start = len(battles)
            for no, battle in zip(range(len(quest['guerrillaBattle']['battles'])), quest['guerrillaBattle']['battles']):
                battles.append(resolve_battle(no + no_start, battle))

        for hime in reward['getItem']:
            if hime['visual'] in ['C3', 'C4']:
                print('getHime: %s' % hime['id'])
        #print(json.dumps(data, indent=4))
        return self.api('quest/end', data)

    def hime_levelup(self, baseOrgId, mtrlOrgIds):
        data = {
            'baseOrgId': baseOrgId,
            'mtrlOrgIds': mtrlOrgIds
        }
        return self.api('hime/levelup', data)

    def item_useFunctionItem(self, itemId):
        data = {
            'itemId': itemId
        }
        return self.api('item/useFunctionItem', data)

    def makeDogfood(self, himeList):
        dogfoodIdSet = [
            [41001, 41002, 41010],          # fire
            [40003, 40004],                 # light
            [42001, 42002, 42006, 42010],   # water
            [43001, 43002, 43003, 43004, 43008, 43084],     # wind
            [44001, 44002],                 # dark
        ]
        for dogfoodId in dogfoodIdSet:
            himeDict = {}

            for hime in himeList:
                if hime['status']['id'] in dogfoodId and hime['fav'] is False:
                    log.info('food: %d Lv%d' % (hime['orgId'], hime['status']['level']))
                    himeDict[hime['orgId']] = hime

            while True:
                baseHime = None
                mtrlHime = None

                for orgId, hime in himeDict.items():

                    if (baseHime is None or hime['status']['level'] < baseHime['status']['level']) and hime['status']['level'] <= 5 and mtrlHime != hime:
                        baseHime = hime
                    if (mtrlHime is None or hime['status']['level'] > mtrlHime['status']['level']) and hime['status']['level'] < 12 and baseHime != hime:
                        mtrlHime = hime

                if baseHime == mtrlHime or baseHime is None or mtrlHime is None:
                    break

                ok, data = self.hime_levelup(baseHime['orgId'], [mtrlHime['orgId']])

                if ok:
                    hime = data['hime']
                    log.info('makeDogfood: Lv%d(%d) + Lv%d(%d) => Lv%d(%d)' % (baseHime['status']['level'], baseHime['orgId'], mtrlHime['status']['level'], mtrlHime['orgId'], hime['status']['level'], hime['orgId']))
                    himeDict[baseHime['orgId']] = hime
                    himeDict.pop(mtrlHime['orgId'])

        log.info('done: Time to feed')
