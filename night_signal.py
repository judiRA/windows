#!/usr/bin/env python3
"""NIGHT SIGNAL - a detective horror game that lives entirely inside a haunted phone.
Single-file game. Needs only pygame. Graphics and sounds are generated in code.
Handwritten notebook pages are saved beside this script as night_signal_notes.json."""
import array
import json
import os
from pathlib import Path
import math
import random
import shutil
import subprocess
import sys

import pygame

IS_ANDROID = bool(os.environ.get('ANDROID_ARGUMENT') or os.environ.get('ANDROID_PRIVATE') or hasattr(sys, 'getandroidapilevel'))
MOBILE_MODE = IS_ANDROID or os.environ.get('NIGHT_SIGNAL_TOUCH') == '1'

def data_directory():
    override=os.environ.get('NIGHT_SIGNAL_DATA_DIR')
    if override:root=Path(override)
    elif IS_ANDROID:
        try:
            from android.storage import app_storage_path
            root=Path(app_storage_path())
        except ImportError:root=Path(os.environ['ANDROID_PRIVATE'])
    else:root=Path(__file__).parent
    root.mkdir(parents=True,exist_ok=True)
    return root

def atomic_json(path,value):
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False))
    temp.replace(path)

def pack_state(value):
    if isinstance(value,dict):return {'$map':[[pack_state(k),pack_state(v)] for k,v in value.items()]}
    if isinstance(value,set):return {'$set':[pack_state(x) for x in value]}
    if isinstance(value,tuple):return {'$tuple':[pack_state(x) for x in value]}
    if isinstance(value,list):return [pack_state(x) for x in value]
    return value

def unpack_state(value):
    if isinstance(value,list):return [unpack_state(x) for x in value]
    if isinstance(value,dict):
        if '$map' in value:return {unpack_state(k):unpack_state(v) for k,v in value['$map']}
        if '$set' in value:return set(unpack_state(x) for x in value['$set'])
        if '$tuple' in value:return tuple(unpack_state(x) for x in value['$tuple'])
        raise ValueError('unknown save structure')
    return value

# ----------------------------------------------------------------------------
# constants
# ----------------------------------------------------------------------------
CW, CH = 216, 384                      # low-res phone canvas (scaled up with crisp pixels)
SX, SY, SW, SH = 9, 14, 198, 286       # glass screen inside the canvas
CAPY, CAPH = 302, 34                   # caption (subtitle) bar
FPS, SR, TMAX = 60, 22050, 119
BG = (7, 9, 13)
PANEL = (18, 25, 32)
PANEL2 = (28, 38, 48)
LINE = (52, 74, 82)
TXT = (206, 222, 214)
DIM = (114, 134, 132)
ACC = (92, 232, 186)
RED = (236, 72, 72)
AMB = (244, 190, 76)
BLUE = (96, 150, 240)
WHITE = (244, 248, 244)
SRC_COL = {'MSG': BLUE, 'CALL': AMB, 'CAM': (200, 130, 255), 'SCENE': ACC, 'PRINT': (255, 140, 120),
           'TALK': (250, 230, 140), 'FILE': DIM, 'LINK': WHITE, 'LAB': ACC, 'MAP': BLUE, 'RECORD': AMB, 'PHOTO': ACC, 'PHONE': AMB, 'WEB': BLUE}
APPS = {'home', 'msg', 'call', 'foot', 'print', 'insp', 'intr', 'notes', 'evid', 'accuse', 'set', 'photos', 'device', 'privacy', 'msgsearch', 'secrets', 'audio'}
F1 = F2 = F3 = None

FIRSTS = ['Mara', 'Elias', 'Nora', 'Victor', 'Ines', 'Tobias', 'Lena', 'Rafe', 'Sylvia', 'Oren', 'Greta', 'Dmitri',
          'Hazel', 'Julian', 'Petra', 'Cal', 'Odessa', 'Felix', 'Wren', 'Anselm', 'Mina', 'Soren']
LASTS = ['Voss', 'Hallam', 'Quill', 'Dray', 'Mercer', 'Okafor', 'Lindqvist', 'Ashby', 'Crane', 'Moreau', 'Vance',
         'Thorne', 'Bellamy', 'Sato', 'Kessler', 'Pruitt', 'Draven', 'Holloway', 'Ng', 'Castellan', 'Rowe', 'Fenwick']
ROLES = ['butler', 'niece', 'business partner', 'family doctor', 'head chef', 'rival', 'gardener', 'lawyer', 'nurse',
         'night janitor', 'accountant', 'old friend', 'neighbor', 'assistant']
MOTIVES = ['was deep in debt to {v}', "was cut out of {v}'s will", 'knew {v} was about to expose an embezzlement',
           'was feuding with {v} over a stolen inheritance', 'was about to be fired by {v}',
           'had been blackmailed by {v} for years', 'lost a bitter lawsuit to {v}', 'was jilted by {v} after a long affair']
SECRETS = ['missing money', 'a forged will', 'a second phone', 'hidden letters', 'a secret loan']
OPENERS = ["You can't keep doing this to me, {v}.", 'We need to talk about what you did.',
           "Don't ignore me. I'm not letting this go.", 'Tell me you did not mean it.',
           'This is the third time you have dodged me.']
REPLIES = ['Not now.', 'Stop texting me.', "You're making a scene.", 'We will settle this soon.']
PEERS = ['the pharmacy', 'a taxi firm', 'their sister', 'the bank helpline', 'an old friend']
COATS = [('red', (205, 50, 50)), ('green', (60, 170, 80)), ('blue', (60, 100, 210)), ('yellow', (220, 200, 60)),
         ('purple', (150, 80, 190)), ('orange', (230, 130, 40)), ('pink', (225, 120, 170)), ('teal', (50, 180, 180))]
SKIN = [(236, 200, 170), (214, 168, 128), (172, 120, 86), (120, 82, 58)]
HAIR = [(30, 24, 22), (86, 56, 32), (180, 150, 90), (150, 150, 156), (120, 36, 30)]
VENUES = [
    dict(name='Harlow Manor', rooms=['Main Hall', 'Study', 'Kitchen', 'Cellar', 'Library', 'Conservatory'],
         weapons=['brass candlestick', 'fireplace poker', 'heavy decanter'], witness='night watchman'),
    dict(name='Blackwater Motel', rooms=['Lobby', 'Room 9', 'Laundry', 'Office', 'Pool Shed', 'Room 4'],
         weapons=['tire iron', 'broken lamp', 'ice bucket'], witness='night clerk'),
    dict(name='Greywick Theatre', rooms=['Foyer', 'Stage', 'Dressing Room', 'Projector Booth', 'Prop Store', 'Pit'],
         weapons=['stage weight', 'prop hammer', 'steel mic stand'], witness='stagehand'),
    dict(name='Ashfield Clinic', rooms=['Reception', 'Ward B', 'Pharmacy', 'Morgue', 'Records Room', 'Staff Room'],
         weapons=['steel tray', 'oxygen tank', 'surgical lamp'], witness='orderly'),
    dict(name='Saltmere Lighthouse', rooms=['Entrance Hall', 'Lamp Room', 'Cellar', 'Keeper Quarters', 'Boathouse', 'Gallery'],
         weapons=['boat hook', 'iron lantern', 'anchor chain'], witness='harbor guard')]
FLAVOR = [('Coat rack', 'Empty hooks and a dusty umbrella.', 'rack'), ('Bookshelf', 'Old ledgers. Nothing out of place.', 'shelf'),
          ('Wastebasket', 'Crumpled receipts, none of them useful.', 'bin'), ('Wall photo', 'A family photo. The eyes seem to follow you.', 'photo'),
          ('Armchair', 'A worn cushion. Still warm?', 'chair'), ('Table', 'A cold cup of tea and a stopped watch.', 'table'),
          ('Window', 'Fogged glass. Something moved outside.', 'window'), ('Locker', 'Locked. Nothing to find here.', 'locker')]
NOISE_CALLS = [('Pizza Corner', 'OUT', '1:05', '"Two large, extra olives, please."'), ('Mom', 'IN', '2:40', '"Call me when you are home safe."'),
               ('Unknown', 'MISSED', '0:00', '(no voicemail)'), ('Clinic desk', 'IN', '0:48', '"Reminder about your appointment."')]
CREEPY = ['i can see your screen', 'check behind you', 'you are not alone in this phone', 'why did you open that file?',
          'he is closer than the camera shows', 'turn off the light. i dare you.']
VOICE = ["I can see you.", "Why are you still looking?", "Don't turn around.", "Nobody is coming to help you.",
         "You missed something. Look again.", "Your phone is not the only thing listening."]
LEVELS = [
    dict(n=3, rh=1, hid=0, hacks=1, inc=('msg', 'call', 'foot', 'exit', 'key', 'print', 'fibre', 'wit')),
    dict(n=4, rh=1, hid=1, hacks=1, inc=('msg', 'call', 'foot', 'exit', 'key', 'print', 'wit')),
    dict(n=4, rh=2, hid=2, hacks=2, inc=('msg', 'foot', 'exit', 'key', 'print', 'wit')),
    dict(n=5, rh=3, hid=3, hacks=2, inc=('msg', 'foot', 'exit', 'print')),
    dict(n=6, rh=4, hid=4, hacks=3, inc=('msg', 'foot', 'print'))]
SLOTS = [(8, 24), (70, 24), (132, 24), (8, 66), (70, 66), (132, 66)]


def clamp(v, a, b):
    return max(a, min(b, v))


def lerp(a, b, t):
    return a + (b - a) * t


def fmt(t):
    m = (20 * 60 + int(t)) % 1440
    return '%02d:%02d' % (m // 60, m % 60)


_wc = {}


def wrap(text, font, w):
    key = (text, w, id(font))
    r = _wc.get(key)
    if r is None:
        r = []
        for para in text.split('\n'):
            line = ''
            for word in para.split(' '):
                t = (line + ' ' + word) if line else word
                if font.size(t)[0] <= w or not line:
                    line = t
                else:
                    r.append(line)
                    line = word
            r.append(line)
        _wc[key] = r
    return r


def fit(s, f, w):
    if f.size(s)[0] <= w:
        return s
    while len(s) > 2 and f.size(s + '..')[0] > w:
        s = s[:-1]
    return s + '..'


# ----------------------------------------------------------------------------
# case generation and validation (pure logic, built on Python's random module)
# ----------------------------------------------------------------------------
# 12 crimes x 5 distinct methods x 5 venues = 300 authored scenario families.
# Identity, room, timing, role, motive, route and trace assignments vary within each.
CRIMES = [
 ('Kidnapping', 'has been abducted; a search team is following the evidence', ['a forged transfer order','a staged maintenance evacuation','a counterfeit taxi booking','a diverted medical transport','a false delivery collection'], ['custody dispute','ransom debt','silencing a witness']),
 ('Missing person', 'has vanished after a deliberately falsified appointment', ['an altered appointment ledger','a forged invitation','a redirected ferry booking','a substituted work roster','a spoofed emergency message'], ['concealing exploitation','preventing testimony','controlling an inheritance']),
 ('Murder', 'was found dead; the scene has been secured', ['a substituted medicine vial','a deliberately loosened railing','a poisoned drink','a tampered electrical fitting','a blow from a heavy tool'], ['concealing theft','revenge for dismissal','preventing an audit']),
 ('Theft', 'reported the disappearance of a sealed collection', ['a substituted shipping label','a copied cabinet key','a swapped exhibition crate','a false disposal order','a disabled inventory sensor'], ['funding a debt','selling a rare object','recovering disputed property']),
 ('Arson', 'reported a deliberately started fire; everyone was evacuated', ['an accelerated waste-bin fire','a tampered heater timer','an ignited solvent trail','a sabotaged emergency battery','a concealed incendiary parcel'], ['insurance proceeds','destroying records','driving out a tenant']),
 ('Blackmail', 'received demands involving private documents', ['a pasted anonymous letter','a spliced audio recording','a stolen backup archive','a manipulated photograph','a planted confidential folder'], ['concealing a loan','forcing a resignation','obtaining a contract']),
 ('Fraud', 'reported an unauthorized transfer of funds', ['a substituted invoice','a forged signature','a cloned payment terminal','a fictitious supplier account','an altered payroll export'], ['covering losses','funding a second business','repaying a hidden debt']),
 ('Stalking', 'reported repeated targeted surveillance', ['a concealed tracking tag','a copied visitor pass','a hidden corridor microphone','a falsified delivery route','a compromised appointment calendar'], ['intimidating a witness','retaliation for rejection','obtaining private information']),
 ('Sabotage', 'reported deliberate damage before an important event', ['a cut control cable','a contaminated coolant bottle','a modified safety relay','a corrupted control script','a swapped calibration gauge'], ['winning a contract','hiding earlier negligence','retaliation for dismissal']),
 ('Extortion', 'received threats against the venue unless money was paid', ['a recorded threat','a coded payment note','a damaged lock and demand','a spoofed alarm notice','a redirected payment envelope'], ['settling a debt','forcing a sale','funding an escape']),
 ('Forgery', 'reported a falsified document affecting ownership', ['a substituted ledger page','a copied seal','a traced signature','a fabricated scan','a backdated delivery receipt'], ['claiming an inheritance','concealing a sale','obtaining access']),
 ('Smuggling', 'reported prohibited fictional artifacts hidden in a shipment', ['a false crate bottom','a switched customs label','a disguised repair shipment','a forged transit permit','a diverted storage manifest'], ['illicit commission','repaying a debt','protecting a buyer'])]
METHODS = [
 dict(label='fiber transfer', sample='snagged fibers', kind='fibre', result='The recovered fibers share the uncommon two-ply weave of issue batch {code}. Several people received this batch. Transfer alone cannot establish when it happened.', lead='Compare the issue register with the route log.', tool='fiber microscopy'),
 dict(label='handwriting', sample='discarded instruction slip', kind='panel', result='Pressure order and the open-loop numeral match writing group {code}. This is a class comparison, not a unique identification.', lead='The carbon copy may help; compare handwriting with the sign-out register.', tool='handwriting comparison'),
 dict(label='audio', sample='recorder memory card', kind='panel', result='The recording contains the paired chime of service device group {code}. Voices are too distorted to identify. The chime was captured during the incident window.', lead='Listen to the background, then check who was issued that equipment.', tool='audio spectrum'),
 dict(label='digital trace', sample='controller export', kind='panel', result='The operation used equipment certificate group {code}. Shared certificates identify equipment pools, not individual operators.', lead='Check the equipment register and independent location logs.', tool='digital trace analysis'),
 dict(label='material residue', sample='sealed residue swab', kind='fibre', result='The residue contains the tracer used in supply lot {code}. Several kits contain this lot; the result is not unique to a person.', lead='Supply issues and travel times may narrow down who could use this lot.', tool='material comparison')]

def _build_case(level, rng):
    n=LEVELS[min(level,5)-1]['n']; vi=rng.randrange(len(VENUES)); ci=rng.randrange(len(CRIMES)); mi=rng.randrange(5)
    V=VENUES[vi]; crime, incident, actions, motives=CRIMES[ci]; M=METHODS[mi]
    rooms=list(V['rooms']); R=rng.choice(rooms[1:]); T=rng.randint(70,100); k=rng.randrange(n)
    names=[a+' '+b for a,b in zip(rng.sample(FIRSTS,n+2),rng.sample(LASTS,n+2))]
    coats=rng.sample(COATS,n); roles=rng.sample(ROLES,n); pats=rng.sample([(a,b,c) for a in range(4) for b in range(3) for c in range(2)],n)
    sus=[dict(id=i,name=names[i],first=names[i].split()[0],role=roles[i],coat=coats[i][0],col=coats[i][1],skin=rng.choice(SKIN),hair=rng.choice(HAIR),pat=pats[i],killer=i==k,motive=rng.choice(motives)) for i in range(n)]
    innoc=[i for i in range(n) if i!=k]; rng.shuffle(innoc)
    # Every individual finding is ambiguous. Their intersection has one answer.
    groups={'record':set(range(n))-{innoc[0]},'lab':{k,innoc[0]},'map':{k,innoc[-1]}}
    code=rng.choice(['K7','M4','R2','V9']); token=rng.choice(['A12','C31','D08','F22'])
    ev=[]
    def E(title,text,src,subj=None,kind='ctx',anchor=None,candidates=None):
        q=dict(id=len(ev),title=title,text=text,src=src,subj=subj,kind=kind,anchor=anchor,found=False)
        if candidates is not None:q['candidates']=sorted(candidates)
        ev.append(q);return q['id']
    threads={}; intr={}; explain={}; calls=[]; cams={'Corridor':[],'Lobby':[]}; insp={r:[] for r in rooms}
    place={i:(R if i==k else rng.choice([r for r in rooms if r!=R])) for i in range(n)}
    claim=dict(place);claim[k]=rng.choice([r for r in rooms if r!=R])
    def hotspot(room,name,text,kind='panel',eid=None,prn=None):
        j=len(insp[room]); insp[room].append(dict(name=name,text=text,kind=kind,rect=(*SLOTS[j],46,34),ev=eid,prn=prn))
        if eid is not None:ev[eid]['anchor']=('insp',(room,j))
    raw=E('Collected: '+M['sample'],'Sealed at '+fmt(T+12)+'. Submit this item to the Forensics Lab.','SCENE')
    recovery = R if mi in (0,4) else rooms[(rooms.index(R)+mi)%len(rooms)]
    hotspot(recovery,M['sample'],'A sealed sample relevant to '+actions[mi]+'. '+M['lead'],M['kind'],raw)
    event=E('Incident window',f'The protected incident log fixes the event at {fmt(T-2)}-{fmt(T+2)}. The method involved {actions[mi]}. Clock drift is under 20 seconds.','SCENE')
    hotspot(R,'Incident log',ev[event]['text']+' A collection note directs you to '+recovery+' for '+M['sample']+'.',eid=event)
    regtext=f'The intact authorization log records permit {token} during {fmt(T-2)}-{fmt(T+2)}. Only the following people held that permit; the sealed issue log lists these authorized users: '+', '.join(sus[i]['name'] for i in sorted(groups['record']))+'.'
    rec=E('Permit audit: '+token,regtext,'RECORD',anchor=('records',0),candidates=groups['record'])
    labtext=M['result'].format(code=code)+' Issue register: '+', '.join(sus[i]['name'] for i in sorted(groups['lab']))+'. Compare with the permit and location audits.'
    lab=E(M['tool'].capitalize(),labtext,'LAB',anchor=('lab',0),candidates=groups['lab'])
    dist=rng.randint(8,14)
    maptext=f'Incident: {R}, {fmt(T-2)}-{fmt(T+2)}. All clocks synchronized. '
    routes=[]
    for i in range(n):
        if i in groups['map']:
            text=f"{sus[i]['name']}: last independently verified at {place[i] if i!=k else claim[i]} at {fmt(T-20)}. Minimum route {dist} min. A gap remains through {fmt(T+8)}; presence at the scene is possible, not proven."
        else:
            text=f"{sus[i]['name']}: attended badge-and-face desk check at {place[i]} at {fmt(T)}. Shortest route to {R}: {dist} min. Cannot reach the scene during the incident."
        routes.append(text)
    mp=E('Synchronized route audit',maptext+'\n\n'+'\n\n'.join(routes),'MAP',anchor=('map',0),candidates=groups['map'])
    records=[dict(title='Permit audit '+token,text=regtext,ev=rec)]
    for i,p in enumerate(sus):
        records.append(dict(title=p['name']+' / '+p['role'],text=f"Fictional personnel file. {p['name']}, {p['role']}. Permit: {token if i in groups['record'] else 'B00'}. Supply / equipment group: {code if i in groups['lab'] else 'S6'}. Declared interest: {p['motive']}. A motive is not evidence of an act.",ev=None))
        E('Outfit: '+p['first'],p['name']+' wears a '+p['coat']+' coat. Clothing can be shared.','FILE',i,anchor=('file',None))
        msgs=[dict(d=0,t=fmt(T-45),x=rng.choice(['The revised schedule has two different times. Which copy is current?','I left the signed copy at reception. The margin notes are not mine.','The equipment desk was busy earlier. Check the issue sheet.']),ev=None),dict(d=1,t=fmt(T-40),x='Keep the original paperwork. We can compare it later.',ev=None),dict(d=0,t=fmt(T-25),x='I noticed '+rng.choice(['the service chime sounded twice.','a carbon sheet under the ledger.','one supply box had a different seal.','the wall clock was being checked.']),ev=None)]
        threads[p['name']]=dict(key=p['name'],role=p['role'],sus=i,msgs=msgs,unread=True)
        qe=E('Statement: '+p['first'],p['name']+' says they were in '+claim[i]+'. This is an unverified account.','TALK',i,anchor=('intr',(i,0)))
        intr[i]=[dict(q='Where were you?',a='I was in '+claim[i]+'. The desk log should show when I arrived.',ev=qe),dict(q='Your connection?',a='I work here as '+p['role']+'. There was a dispute about '+p['motive']+'.',ev=None),dict(q='Anything unusual?',a=M['lead'],ev=None),dict(q='Present evidence...',a='That needs checking against the original records. I stand by my account.',ev=None)]
        explain[i]='People used those objects before today. Check the dates and independent logs.'
        for cam,t0,t1,kind,room in [('Corridor',T-23+i,T-21+i,'enter',claim[i]),('Lobby',T+12+i,T+14+i,'leave',rooms[0])]:
            cams[cam].append(dict(cam=cam,t0=t0,t1=t1,who=i,kind=kind,room=room,text=f"a {p['coat']}-coated figure crosses toward {room}; face not resolved",ev=None))
    # A second route through the investigation: CCTV corroborates earlier
    # handling, without identifying the offender at the incident.
    visitor=innoc[0]
    ce=E('Earlier scene visit',f"A {sus[visitor]['coat']}-coated visitor enters {R} at {fmt(T-35)} and leaves at {fmt(T-30)}. This is earlier than the incident; compare the outfit file and handling history.",'CAM',visitor,'ctx',('foot',('Corridor',len(cams['Corridor']))))
    cams['Corridor'].append(dict(cam='Corridor',t0=T-35,t1=T-33,who=visitor,kind='enter',room=R,text='an earlier visitor enters '+R,ev=ce))
    cams['Corridor'].append(dict(cam='Corridor',t0=T-31,t1=T-30,who=visitor,kind='exit',room=R,text='the earlier visitor leaves '+R,ev=None))
    # Misleading prints are always contextual; their owner may be innocent.
    owner=rng.choice(innoc if rng.random()<.75 else list(range(n))); quality=rng.choice(['partial','contaminated','old'])
    pe=E('Print comparison',f"Ridge features are compatible with {sus[owner]['name']}. Quality: {quality}. A fingerprint cannot be dated and is not proof of participation.",'PRINT',owner,'sus',('prnt',0))
    prints=[dict(id=0,where='the shared work tray',target=owner,lifted=False,done=False,tries=0,ev=pe)]
    hotspot(R,'Shared work tray','A handled tray with a partial ridge impression. Preserve it for comparison.','handle',prn=0)
    context=E('Tray handling history',f"A dated maintenance photo shows {sus[owner]['name']} handling this tray yesterday. The collection sheet also records overlapping glove powder. Compare location logs before drawing conclusions.",'SCENE',owner)
    hotspot(rooms[0],'Maintenance photo',ev[context]['text'],eid=context)
    for room in rooms:
        while len(insp[room])<3:
            f=rng.choice(FLAVOR);hotspot(room,f[0],f[1],f[2])
    witness=names[-1]
    tips=[]
    for who,line in [(witness,'I work the front desk. '+M['lead']), (sus[rng.choice(innoc)]['name'],'I handled that tray yesterday. There should be a maintenance photo.'),(sus[k]['name'],'The schedule had been revised. Please compare the original times with the route logs.')]:
        tips.append(dict(who=who,dir='IN',t=fmt(T+18),dur='0:24',lines=['This is '+who+'. '+line],info='Incoming interview call; preserved transcript',ev=None,heard=False))
    calls.append(dict(tips[0]));threads[witness]=dict(key=witness,role=V['witness'],sus=None,msgs=[dict(d=0,t=fmt(T+5),x='The incident log should fix the time. '+M['lead'],ev=None)],unread=True)
    return dict(level=level,scenario=(ci,mi,vi),crime=crime,venue=V['name'],rooms=rooms,lobby=rooms[0],R=R,weapon=actions[mi],T=T,victim=names[-2],vfirst=names[-2].split()[0],wit=witness,sus=sus,killer=k,place=place,claim=claim,clr={},rh=[],rh_t={},ev=ev,threads=threads,calls=calls,tips=tips,cams=cams,insp=insp,prints=prints,intr=intr,explain=explain,hacks=LEVELS[min(level,5)-1]['hacks'],coatsof=sus[k]['coat'],records=records,routes=routes,map_ev=mp,lab=[dict(title=M['tool'],raw=raw,ev=lab)],proof=[rec,lab,mp],
      brief=f"{crime.upper()} / {V['name']}\n\n{names[-2]} {incident}. The initial scene is {R}.\n\nWindow: {fmt(T-2)}-{fmt(T+2)}. Inspect the scene, search Police Records, compare Map routes and submit samples to the Lab.\n\nCombine three independent findings. No single trace identifies the culprit.",
      solution=f"{sus[k]['name']} was responsible for {actions[mi]}. The permit audit, {M['label']} and travel window overlap only for this person. Motive: {sus[k]['motive']}. The tray print alone was inconclusive.")

def make_case(level, rng):
    c=_build_case(level,rng)
    old=[c['ev'][i] for i in c['proof']]
    groups=[set(e['candidates']) for e in old]
    for e in old:
        e.pop('candidates',None)
        e.update(title='Archive placeholder',text='Superseded archive index.',anchor=('internal',None))
    c['photo_seen'],c['device_seen'],c['web_seen'],c['message_seen']=set(),set(),set(),set()
    c['badge_code']=rng.choice(['A12','C31','D08']);c['device_code']=rng.choice(['K7','M4','R2'])
    c['badges']=[c['badge_code'] if i in groups[0] else 'B00' for i in range(len(c['sus']))]
    c['artifacts']={'photo':{},'device':{},'web':{}}
    c['device_logs']=[];c['device_messages']=[];c['routes']=[]
    def add(title,text,src,i,anchor):
        eid=len(c['ev']);c['ev'].append(dict(id=eid,title=title,text=text,src=src,subj=i,kind='ctx',anchor=anchor,found=False));return eid
    offset=rng.choice([-9,-6,7,11]);c['clock_offset']=offset
    c['incident_ev']=next(e['id'] for e in c['ev'] if e['title']=='Incident window')
    e=c['ev'][c['incident_ev']]
    e['title']='Scene instrument log'
    e['text']=f"Door logger display: {fmt(c['T']-2+offset)}-{fmt(c['T']+2+offset)}. Its clock has not been synchronized. Access group: {c['badge_code']}. Operation export: {c['device_code']}. Physical examination indicates {c['weapon']}. Check the technician's message before trusting these times."
    clocktext=f"The door logger ran {abs(offset)} minutes {'ahead of' if offset>0 else 'behind'} the station clock all evening. The public event pages and phone messages already use station time. Do not apply the correction to those."
    th=c['threads'][c['wit']]
    c['clock_ev']=add('Technician message',clocktext,'MSG',None,('msg',(c['wit'],len(th['msgs']))))
    th['msgs'].append(dict(d=0,t=fmt(c['T']+20),x=clocktext,ev=c['clock_ev']))
    for i,p in enumerate(c['sus']):
        badge=c['badges'][i]
        c['artifacts']['photo'][i]=add('Portrait / '+p['first'],f"Portrait stamped {fmt(c['T']-40)}. {p['name']} wears badge {badge}. The badge belongs to an access group shared by several staff. Its presence does not date a visit.",'PHOTO',i,('photos',i))
        effective=c['device_code'] if i in groups[1] else 'S6'
        switch=c['T']+rng.choice([-22,23])
        previous,current=(effective,'Q8') if switch>c['T'] else ('Q8',effective)
        log=f"Archive for {p['name']}. Previous equipment group: {previous}. Replacement group: {current}. Both entries are retained after a change. The service conversation records when the change took effect."
        msg=f"SERVICE DESK\nMessage sent: {fmt(c['T']-45)} station time.\n\nCHANGEOVER TIME: {fmt(switch)} station time.\n\nUse previous group {previous} BEFORE {fmt(switch)}. Use replacement group {current} AT {fmt(switch)} and AFTER.\n\n{p['first']}: I kept the earlier entry too, as requested."
        c['device_logs'].append(log);c['device_messages'].append(msg)
        c['artifacts']['device'][i]=add('Handset archive / '+p['first'],log+'\n\n'+msg,'PHONE',i,('drawer',i))
        travel=rng.randint(9,15)
        stamp=c['T']-25 if i in groups[2] else c['T']
        route=f"Public attendance archive: {p['name']} was checked in face-to-face at {c['claim'][i]}, {fmt(stamp)} station time. The only route to {c['R']} takes at least {travel} minutes. The desk has no later check-out record."
        c['routes'].append(route)
        c['artifacts']['web'][i]=add('Public entry / '+p['first'],route,'WEB',i,('laptop',i))
    c['proof']=[c['artifacts'][key][c['killer']] for key in ('photo','device','web')]
    c['eligible_groups']=[sorted(g) for g in groups]
    for spots in c['insp'].values():
        for h in spots:
            if h['name']=='Incident log':h['text']=e['text']
            if h['ev']==c['lab'][0]['raw']:
                h['text']='Preserved material. The operation export retains identifier '+c['device_code']+'. This label may have changed hands; check the service messages.'
                c['ev'][h['ev']]['text']=h['text']
    for i,qs in c['intr'].items():qs[2]['a']='The service labels were being replaced that night. The replacement time matters.'
    for th in c['threads'].values():
        for m in th['msgs']:
            if th['sus'] is None and m['ev'] is None:m['x']='The door logger was not on station time. I asked the technician to send the correction.'
    c['brief']=f"{c['crime'].upper()} / {c['venue']}\n\n{c['victim']}: {CRIMES[c['scenario'][0]][1]}.\n\nScene: {c['R']}. The incident time needs verification. Read the instrument log and technician's message. Investigate portraits, handset conversations and public archives.\n\nYour accusation must explain who, when and how."
    times=[c['T'],c['T']+offset,c['T']-offset,c['T']+30];rng.shuffle(times);c['time_choices']=times
    methods=list(CRIMES[c['scenario'][0]][2]);rng.shuffle(methods);c['method_choices']=methods
    c['solution']=f"{c['sus'][c['killer']]['name']} carried out {c['weapon']} during {fmt(c['T']-2)}-{fmt(c['T']+2)} station time. Correcting the logger clock puts the event inside this person's travel opportunity and active device assignment. Their portrait also carries the logged access group. Motive: {c['sus'][c['killer']]['motive']}."
    return c


def proof_valid(c,suspect,ids,when=None,method=None):
    if suspect!=c['killer'] or when!=c['T'] or method!=c['weapon']:return False
    if set(ids)!=set(c['proof']):return False
    return all(c['ev'][i]['found'] for i in ids+[c['incident_ev'],c['clock_ev']])


def validate(c):
    bad=[]
    if set.intersection(*(set(g) for g in c['eligible_groups']))!={c['killer']}:bad.append('ambiguous solution')
    if any(len(g)<2 for g in c['eligible_groups']):bad.append('single source giveaway')
    if any(e['anchor'] is None for e in c['ev']):bad.append('unreachable evidence')
    return bad

TUTORIAL_PAGES = [('Welcome / controls', 'Solve five cases by reading and connecting observations. Click once; scroll long reports. Arrow goes back, circle goes home, speaker or M mutes. PUT DOWN opens your desk. The title TUTORIAL button starts optional guidance from Pip; normal cases do not start the tutorial.'), ('Your desk', 'Click the phone to pick it up. Click the notebook to write your own notes. Click the laptop to fill the window with its search screen. Click the drawer to inspect secured suspect phones.\n\nEach desk screen has a BACK TO DESK button. Esc also returns to the desk.'), ('Notebook', 'Click the notebook and type freely. Backspace deletes; Enter starts a new line. Scroll to read longer notes.\n\nNotes are saved beside the game in night_signal_notes.json, grouped by case. PREVIOUS and NEXT switch pages. Notes survive restarting. Mobile also saves campaign progress.'), ('Photos / zoom', 'Open Photos, choose a portrait, zoom to 2x or 4x and click the badge. This saves that individual photograph. Read the badge code and photograph time. No automatic comparison or suspect shortlist is generated.'), ('Laptop search', 'Put down the phone. Open the laptop and Google, then search a name or occupation. Each profile contains a raw public timestamp and a minimum journey time. Work out whether that person could reach the scene during the corrected incident window. Opening every profile does not produce a verdict.'), ('Suspect phones', 'Open a handset in the drawer. Read BOTH Messages and Activity. Activity lists previous and replacement device groups. The service message tells you when to switch between them. Decide which group was active at the incident time. Reading both saves that individual handset archive.'), ('Inspect / CCTV', 'Inspect rooms and objects for the incident window, handling history and trace identifiers. Evidence is collected automatically when you read relevant objects.\n\nIn CCTV, choose a camera. PLAY/PAUSE, -1/+1 minute, speed and RESTART control playback. Drag the bar or jump to a motion clip. Viewing a relevant clip collects evidence. A coat or early visit alone proves little.'), ('Prints / conversations', 'LIFT PRINT from a scene object, then compare ridge shape, spacing and scars in Prints. Matches are provisional: prints may be old, partial or contaminated. Read the maintenance photo.\n\nMessages, Calls and Interviews offer supporting clues. Answered incoming calls are saved for replay. Missing a call cannot block the case. Suspects never need to confess.'), ('Evidence / accuse', 'Inspect the scene instrument log, then read the technician message in your investigation phone. Correct the logger time to station time. Do not correct timestamps that already use station time. Compare portrait badges, active device groups and public travel times.\n\nChoose a suspect in Accuse. Their collected portrait, handset archive and public entry load automatically. Tap a missing row to find it. Click EXPLAIN and choose the incident window and method supported by the scene. A complete unsupported reconstruction costs one chance. The game never tells you which answer was wrong.'), ('Interrogation room', 'Put down the phone. Click INTERROGATION ROOM at the top-left of the desk. Choose a suspect to seat across from you. Selecting someone is not an accusation.\n\nAsk about their whereabouts and connection to the case. Find their portrait, handset archive and public entry to unlock specific follow-ups. Read the recorded answer and scroll if needed. Statements are saved in Evidence and the room transcript; verify them independently. Use CHOOSE SUSPECT or BACK TO DESK to leave.'), ('Hacks / settings', 'Sequence: watch and repeat the colored pads. Nodes: tap 1 to 6 before time expires. Virus: click every red bug. Failures simply restart the puzzle.\n\nSettings controls sound, voices and scare frequency. Subtitles stay on. Solve five cases to complete a run. Notebook pages persist. Mobile also saves campaign progress. The next tutorial page tracks the current case.')]
TUTORIAL_PAGES.insert(0, ('Your investigation / why each step matters',
    '1. Read the case brief: learn the crime and location. Open Inspect and read the incident log: it supplies scene identifiers, method and a LOCAL time.\n\n'
    '2. Read Messages and the technician note: convert the logger time to station time. A fast clock means subtract; a slow clock means add. Example: 21:10, five minutes fast, means 21:05. Already-station timestamps stay unchanged.\n\n'
    '3. Open Photos, choose a portrait, zoom and tap its badge. Compare the individual code with the scene log. This establishes a possible connection, not guilt.\n\n'
    '4. Put down the phone and open the drawer. Read each handset\'s Messages AND Activity. The service message tells you when a device assignment changed. Use the group active at the corrected incident time.\n\n'
    '5. Open the laptop, then Google. Search a suspect and read their public timeline. Add the minimum journey duration to their recorded time. Compare arrival with the incident window; this checks whether their alibi is possible.\n\n'
    '6. Use CCTV, prints and interviews to check context. Old or contaminated prints can mislead. Question suspects in the interrogation room and compare their answers with independent evidence.\n\n'
    '7. Write your reasoning in the desk notebook. Find the ONE person whose badge, active device and travel opportunity fit together. You must read the details; opening every app does not solve the case.\n\n'
    '8. Open Accuse. Select that person; their collected portrait, handset archive and public entry load automatically. Select EXPLAIN, then the corrected incident window and scene-supported method. Submit only when your reconstruction agrees with the evidence.\n\n'
    'Tap Pip during the guided tutorial to read these pages. NEXT/PREV turns pages; LEARN WITH PIP returns to hands-on guidance. X beside Pip hides the bot. Normal new games never enable Pip automatically.'))

TUTORIAL_PAGES.append(('Experienced / extra investigation tools',
    'Choose Experienced on the title before starting a new game. These extra leads add context; the final case still needs a consistent reconstruction.\n\n'
    'PHOTO SECRETS: Open a portrait, then BACKGROUND / HIDDEN DETAILS. Use arrows to choose an object; tap its label for 2x or 4x zoom, then tap the object. Its full exhibit appears in Evidence. Compare reflections, receipts, clocks, shoes and borrowed objects.\n\n'
    'CONTRADICTIONS: At the interrogation desk, ask about anything unusual before the portrait. Find that suspect\'s conflicting photo detail, then use CHALLENGE to show it. Their revised account gives a phrase to search in their handset. A changed story alone is not guilt.\n\n'
    'MESSAGE SEARCH: Messages on your investigation phone searches recovered threads. In a drawer handset, Messages has SEARCH THIS PHONE. Type a phrase and tap a match to return to its original conversation. Check surrounding context.\n\n'
    'BOARD: Put down the phone and open EVIDENCE BOARD. + EXHIBIT chooses a found clue; SAVE THREAD FOR BOARD pins a conversation. + NOTE copies your current notebook page. Drag pins or select one and tap empty space in MOVE mode. CONNECT lets you select two pins to add a thread; repeat that pair to remove it. UNPIN removes the selected card. Scroll its text below the board. Connections are yours, with no correctness score.\n\n'
    'AUDIO: Calls > AUDIO INVESTIGATION replays a background recording. Read the facilities sound reference in Evidence, then compare the bell, machine or platform sound. Captions contain the same audible information. The recording predates the incident and cannot prove guilt.\n\n'
    'DESK: Occasional drawer movement, a waking laptop or knocks add atmosphere. They never remove evidence or change the solution.'))


# ----------------------------------------------------------------------------
# sound (generated in code)
# ----------------------------------------------------------------------------
SND = {}


def build_sounds(chan):
    sin, tau, rnd = math.sin, math.tau, random.uniform

    def gen(dur, fn, vol=1.0):
        n = int(SR * dur)
        out = array.array('h')
        for i in range(n):
            v = int(clamp(fn(i / SR, i / n), -1, 1) * 30000 * vol)
            out.append(v)
            if chan == 2:
                out.append(v)
        return pygame.mixer.Sound(buffer=out.tobytes())

    SND['click'] = gen(.05, lambda t, p: .5 * sin(tau * 880 * t) * (1 - p), .6)
    SND['back'] = gen(.06, lambda t, p: .5 * sin(tau * 520 * t) * (1 - p), .6)
    SND['good'] = gen(.3, lambda t, p: .5 * sin(tau * (520 + 520 * p) * t) * (1 - p), .7)
    SND['bad'] = gen(.35, lambda t, p: .5 * sin(tau * (200 - 80 * p) * t) * (1 if sin(tau * 30 * t) > 0 else .3) * (1 - p), .8)
    SND['type'] = gen(.02, lambda t, p: .3 * rnd(-1, 1) * (1 - p), .5)
    SND['static'] = gen(.5, lambda t, p: .5 * rnd(-1, 1) * (1 - p * .5), .6)
    SND['glitch'] = gen(.25, lambda t, p: .5 * (1 if sin(tau * rnd(100, 900) * t) > 0 else -1) * (1 - p), .6)
    SND['ring'] = gen(1.2, lambda t, p: .25 * (sin(tau * 440 * t) + sin(tau * 480 * t)) * (1 if p < .7 else 0), .8)
    SND['whisper'] = gen(1.1, lambda t, p: .35 * rnd(-1, 1) * abs(sin(tau * 3.1 * t)), .6)
    SND['scare'] = gen(.8, lambda t, p: (.6 * rnd(-1, 1) + .5 * (1 if sin(tau * (180 + 700 * (1 - p)) * t) > 0 else -1)) * (1 - p * .6), .8)
    SND['hum'] = gen(2.0, lambda t, p: .25 * sin(tau * 55 * t) + .15 * sin(tau * 82.5 * t) + .05 * sin(tau * 165 * t) * sin(tau * t), .35)
    SND['bell_clue']=gen(2.4,lambda t,p: .45*sin(tau*660*t)*math.exp(-9*(t%1.2)),.7)
    SND['machine_clue']=gen(2.4,lambda t,p: .25*sin(tau*90*t)*(1 if (t% .6)<.3 else .1),.7)
    SND['train_clue']=gen(2.4,lambda t,p: .18*sin(tau*180*t)+.3*sin(tau*(740 if (t%1)<.5 else 520)*t)*(1 if t<1 else .1),.7)
    SND['knock']=gen(.9,lambda t,p: .5*rnd(-1,1)*math.exp(-35*(t%.3)),.5)
    for j, f in enumerate((262, 330, 392, 523)):
        SND['p%d' % j] = gen(.25, lambda t, p, f=f: .5 * sin(tau * f * t) * (1 - p * .5), .7)


# ----------------------------------------------------------------------------
# pixel drawing helpers
# ----------------------------------------------------------------------------
def draw_print(s, cx, cy, pat, r=24, col=ACC, smudge=None):
    t, sp, scar = pat
    gap = (3, 4, 5)[sp]
    old = s.get_clip()
    s.set_clip(old.clip(pygame.Rect(cx - r, cy - r, 2 * r, 2 * r)))
    for rr in range(gap, r + 2, gap):
        if t == 0:
            pygame.draw.circle(s, col, (cx, cy), rr, 1)
        elif t == 1:
            pygame.draw.ellipse(s, col, (cx - rr // 2, cy - rr, rr, rr * 2 - rr // 3), 1)
        elif t == 2:
            pygame.draw.arc(s, col, (cx - r - 4, cy + r // 2 - rr, 2 * r + 8, 2 * rr), 0, math.pi, 1)
        else:
            q = min(rr, r * 2 // 3)
            pygame.draw.circle(s, col, (cx - r // 3, cy), q, 1)
            pygame.draw.circle(s, col, (cx + r // 3, cy), q, 1)
    if scar:
        pygame.draw.line(s, (8, 12, 14), (cx - r, cy - r // 3), (cx + r, cy + r // 4), 2)
    for (x, y, w, h) in (smudge or []):
        pygame.draw.ellipse(s, (8, 12, 14), (cx + x, cy + y, w, h))
    s.set_clip(old)


def draw_portrait(s, r, p):
    pygame.draw.rect(s, (14, 20, 26), r)
    cx, by = r.centerx, r.bottom
    u = r.w / 56.0
    pygame.draw.polygon(s, p['col'], [(cx - int(24 * u), by), (cx - int(12 * u), by - int(18 * u)), (cx + int(12 * u), by - int(18 * u)), (cx + int(24 * u), by)])
    pygame.draw.rect(s, p['skin'], (cx - int(4 * u), by - int(22 * u), int(8 * u), int(6 * u)))
    hy = by - int(34 * u)
    pygame.draw.ellipse(s, p['skin'], (cx - int(11 * u), hy - int(12 * u), int(22 * u), int(26 * u)))
    pygame.draw.rect(s, p['hair'], (cx - int(12 * u), hy - int(14 * u), int(24 * u), int(9 * u)))
    for ex in (-5, 3):
        pygame.draw.rect(s, (10, 10, 12), (cx + int(ex * u), hy - int(2 * u), max(1, int(2 * u)), max(1, int(2 * u))))
    pygame.draw.line(s, (80, 40, 40), (cx - int(3 * u), hy + int(7 * u)), (cx + int(3 * u), hy + int(7 * u)))
    pygame.draw.rect(s, LINE, r, 1)


def draw_face(s, cx, cy, sz, t):
    j = int(math.sin(t * 90) * 3)
    pygame.draw.ellipse(s, (214, 220, 208), (cx - sz // 2 + j, cy - sz // 2, sz, int(sz * 1.25)))
    for ex in (-1, 1):
        pygame.draw.ellipse(s, (4, 4, 6), (cx + ex * sz // 5 - sz // 8 + j, cy - sz // 8, sz // 4, sz // 3))
        pygame.draw.circle(s, (230, 40, 40), (cx + ex * sz // 5 + j, cy + sz // 24), max(1, sz // 30))
    pygame.draw.ellipse(s, (4, 4, 6), (cx - sz // 5 + j, cy + sz // 4, sz * 2 // 5, sz // 2))
    for k in range(5):
        x = cx - sz // 5 + sz // 12 + k * sz // 12 + j
        pygame.draw.line(s, (210, 214, 200), (x, cy + sz // 4), (x, cy + sz // 4 + sz // 10))


def draw_figure(s, x, yb, sc, col, sit=False):
    dim = tuple(int(c * .8) for c in col)
    hh = int(26 * sc * (0.7 if sit else 1.0))
    w = max(3, int(10 * sc))
    hr = max(2, int(4 * sc))
    top = yb - hh
    leg = 0 if sit else int(8 * sc)
    pygame.draw.rect(s, dim, (x - w // 2, top + hr * 2, w, max(2, hh - hr * 2 - leg)))
    pygame.draw.circle(s, (205, 205, 200), (x, top + hr), hr)
    if leg:
        pygame.draw.rect(s, (22, 22, 28), (x - w // 2 + 1, yb - leg, max(1, w // 2 - 1), leg))
        pygame.draw.rect(s, (22, 22, 28), (x + 1, yb - leg, max(1, w // 2 - 1), leg))


def door_pos(r, j):
    z = (0.0, 0.0, 0.45, 0.45, 0.78)[j]
    cx = r.centerx
    vy = r.y + int(r.h * .42)
    left = j % 2 == 0
    xw = lerp(r.x + 6, cx - 26, z) if left else lerp(r.right - 6, cx + 26, z)
    yb = lerp(r.bottom - 4, vy + 22, z)
    return xw, yb, 1.0 - z, left


def draw_cam(s, r, cam, t, c, now, glitch):
    # Fixed elevated corner camera: project ground coordinates through a
    # tilted perspective camera, rather than moving the camera with the actor.
    old=s.get_clip();s.set_clip(old.clip(r));s.fill((12,20,23),r)
    def project(x,z,h=0):
        depth=3.5+z+.32*x
        return (int(r.x+r.w*.16+r.w*.91*(x+.38*z)/depth),
                int(r.y+r.h*.10+r.h*(3.6-h)/depth))
    def poly(points,color):pygame.draw.polygon(s,color,[project(*p) for p in points])
    poly([(0,0,0),(6,0,0),(6,9,0),(0,9,0)],(29,39,40))
    poly([(0,0,0),(0,9,0),(0,9,3),(0,0,3)],(41,51,51))
    poly([(0,9,0),(6,9,0),(6,9,3),(0,9,3)],(34,44,49))
    for z in range(10):pygame.draw.line(s,(48,59,58),project(0,z),project(6,z))
    for x in range(7):pygame.draw.line(s,(48,59,58),project(x,0),project(x,9))
    for j in range(5 if cam=='Corridor' else 2):
        z=1+j*1.5
        poly([(0,z,0),(0,z+1,0),(0,z+1,2.2),(0,z,2.2)],(67,58,48))
        s.blit(F1.render(str(j+1),True,AMB),project(0,z+.5,1.7))
    if cam=='Lobby':
        poly([(2,5,0),(5,5,0),(5,7,0),(2,7,0)],(69,51,46))
        poly([(2,5,0),(5,5,0),(5,5,.6),(2,5,.6)],(85,66,55))
    visible=[g for g in c['cams'][cam] if g['t0']<=t<=g['t1']]
    for g in sorted(visible,key=lambda g:g['who'],reverse=True):
        p=(t-g['t0'])/max(.01,g['t1']-g['t0'])
        z=lerp(1,7,p if g['kind'] in ('enter','arrive') else 1-p)
        x=2+(g['who']%3)*.9
        px,py=project(x,z);_,head=project(x,z,1.7)
        col=c['sus'][g['who']]['col'] if g['who']>=0 else DIM
        pygame.draw.ellipse(s,(9,15,17),(px-5,py-2,12,4))
        draw_figure(s,px,py,max(.3,(py-head)/26),col,g['kind']=='sit')
    if glitch:
        rnd=random.Random(int(t*60))
        for _ in range(35):s.set_at((rnd.randrange(r.x,r.right),rnd.randrange(r.y,r.bottom)),(80,100,98))
    pygame.draw.rect(s,(8,15,17),(r.x,r.y,r.w,12))
    stamp='CAM %02d  %s:%02d  REC' % (1 if cam=='Corridor' else 2,fmt(t),int(t%1*60))
    s.blit(F1.render(stamp,True,ACC),(r.x+3,r.y+2))
    pygame.draw.circle(s,RED,(r.right-5,r.y+6),2)
    s.set_clip(old);pygame.draw.rect(s,LINE,r,1)


def draw_obj(s, kind, r, hover):
    base = (60, 76, 80) if hover else (40, 52, 58)
    pygame.draw.rect(s, (10, 14, 18), r.inflate(2, 2))
    if kind == 'weapon':
        pygame.draw.rect(s, (30, 22, 24), r)
        pygame.draw.line(s, (170, 170, 180), (r.x + 6, r.bottom - 6), (r.right - 6, r.y + 6), 4)
        pygame.draw.circle(s, (150, 30, 30), (r.right - 8, r.y + 8), 3)
    elif kind in ('handle', 'locker', 'window'):
        pygame.draw.rect(s, base, r)
        pygame.draw.rect(s, (110, 120, 120), r, 1)
        if kind == 'handle':
            pygame.draw.circle(s, (200, 180, 90), (r.right - 10, r.centery), 4)
        elif kind == 'window':
            pygame.draw.line(s, (110, 120, 120), (r.centerx, r.y), (r.centerx, r.bottom))
            pygame.draw.line(s, (110, 120, 120), (r.x, r.centery), (r.right, r.centery))
        else:
            pygame.draw.line(s, (110, 120, 120), (r.centerx, r.y + 3), (r.centerx, r.bottom - 3))
    elif kind == 'panel':
        pygame.draw.rect(s, base, r.inflate(-14, -4))
        pygame.draw.rect(s, (14, 20, 24), (r.centerx - 8, r.y + 10, 16, 8))
        pygame.draw.circle(s, ACC, (r.centerx + 12, r.y + 8), 2)
    elif kind == 'fibre':
        pygame.draw.rect(s, base, r.inflate(-20, 0))
        for k in range(4):
            pygame.draw.line(s, (200, 200, 190), (r.x + 12, r.y + 6 + k * 6), (r.x + 20 + k * 3, r.y + 10 + k * 6))
    else:
        pygame.draw.rect(s, base, r)
        pygame.draw.rect(s, (96, 110, 112), r, 1)
        pygame.draw.rect(s, (24, 32, 36), (r.x + 4, r.y + 4, r.w - 8, r.h // 3))
        if kind in ('table', 'chair', 'rack'):
            pygame.draw.line(s, (96, 110, 112), (r.x + 4, r.bottom), (r.x + 4, r.bottom + 4))
            pygame.draw.line(s, (96, 110, 112), (r.right - 4, r.bottom), (r.right - 4, r.bottom + 4))


def draw_photo(s, r, room, mn):
    h = sum(ord(ch) for ch in room)
    base = (22 + h % 20, 30 + (h * 3) % 18, 34 + (h * 7) % 18)
    old = s.get_clip()
    s.set_clip(old.clip(r))
    pygame.draw.rect(s, base, r)
    fy = r.y + int(r.h * .66)
    pygame.draw.rect(s, tuple(int(q * .55) for q in base), (r.x, fy, r.w, r.bottom - fy))
    for k in range(0, r.w, 14):
        pygame.draw.line(s, tuple(int(q * .45) for q in base), (r.x + k - int(mn[0] * 2), fy), (r.x + k * 2 - r.w // 2, r.bottom))
    ox = int(mn[0] * -3)
    pygame.draw.rect(s, (14, 20, 30), (r.x + 130 + ox, r.y + 8, 36, 28))
    pygame.draw.circle(s, (120, 130, 150), (r.x + 154 + ox, r.y + 16), 4)
    pygame.draw.rect(s, (70, 80, 82), (r.x + 130 + ox, r.y + 8, 36, 28), 1)
    pygame.draw.rect(s, (46, 40, 36), (r.x + 12 + ox, r.y + 8, 24, 16), 1)
    s.set_clip(old)


def draw_icon(s, kind, r):
    cols = dict(msg=(40, 110, 200), call=(40, 160, 90), foot=(130, 70, 190), print=(190, 90, 70), insp=(60, 150, 160),
                intr=(180, 140, 50), notes=(170, 160, 60), evid=(60, 120, 110), accuse=(190, 50, 60), set=(90, 100, 110), photos=(80,140,110))
    pygame.draw.rect(s, cols[kind], r, border_radius=6)
    pygame.draw.rect(s, tuple(min(255, q + 60) for q in cols[kind]), r, 1, border_radius=6)
    cx, cy = r.center
    w = (240, 245, 240)
    if kind == 'photos':
        s.blit(F2.render('P',True,w),(cx-5,cy-7))
    elif kind == 'msg':
        pygame.draw.rect(s, w, (cx - 11, cy - 9, 22, 14), border_radius=3)
        pygame.draw.polygon(s, w, [(cx - 6, cy + 4), (cx - 8, cy + 11), (cx + 1, cy + 4)])
    elif kind == 'call':
        pygame.draw.line(s, w, (cx - 8, cy + 8), (cx + 8, cy - 8), 5)
        pygame.draw.circle(s, w, (cx - 8, cy + 8), 4)
        pygame.draw.circle(s, w, (cx + 8, cy - 8), 4)
    elif kind == 'foot':
        pygame.draw.rect(s, w, (cx - 12, cy - 7, 17, 14), border_radius=2)
        pygame.draw.polygon(s, w, [(cx + 7, cy), (cx + 13, cy - 6), (cx + 13, cy + 6)])
    elif kind == 'print':
        for k in (4, 8, 12):
            pygame.draw.ellipse(s, w, (cx - k, cy - k, 2 * k, 2 * k), 1)
    elif kind == 'insp':
        pygame.draw.circle(s, w, (cx - 3, cy - 3), 8, 2)
        pygame.draw.line(s, w, (cx + 3, cy + 3), (cx + 11, cy + 11), 3)
    elif kind == 'intr':
        pygame.draw.circle(s, w, (cx, cy - 4), 6, 2)
        pygame.draw.arc(s, w, (cx - 10, cy + 2, 20, 16), 0, math.pi, 2)
    elif kind == 'notes':
        pygame.draw.rect(s, w, (cx - 9, cy - 11, 18, 22), 1)
        for k in range(4):
            pygame.draw.line(s, w, (cx - 6, cy - 6 + k * 5), (cx + 6, cy - 6 + k * 5))
    elif kind == 'evid':
        for pt in ((cx - 8, cy - 6), (cx + 8, cy - 4), (cx, cy + 8)):
            pygame.draw.circle(s, w, pt, 3)
        pygame.draw.lines(s, w, True, [(cx - 8, cy - 6), (cx + 8, cy - 4), (cx, cy + 8)], 1)
    elif kind == 'accuse':
        pygame.draw.polygon(s, w, [(cx, cy - 11), (cx + 12, cy + 9), (cx - 12, cy + 9)], 2)
        pygame.draw.line(s, w, (cx, cy - 4), (cx, cy + 2), 2)
        pygame.draw.rect(s, w, (cx - 1, cy + 5, 2, 2))
    else:
        pygame.draw.circle(s, w, (cx, cy), 8, 2)
        for a in range(0, 360, 60):
            pygame.draw.line(s, w, (cx + int(math.cos(math.radians(a)) * 8), cy + int(math.sin(math.radians(a)) * 8)),
                             (cx + int(math.cos(math.radians(a)) * 12), cy + int(math.sin(math.radians(a)) * 12)), 2)


# ----------------------------------------------------------------------------
# the game
# ----------------------------------------------------------------------------
class Game:
    def __init__(self):
        global F1, F2, F3
        try:
            pygame.mixer.pre_init(SR, -16, 1, 512)
        except Exception:
            pass
        os.environ.setdefault("SDL_MOUSE_FOCUS_CLICKTHROUGH", "1")
        pygame.init()
        pygame.display.set_caption('NIGHT SIGNAL')
        info = pygame.display.Info()
        h = max(560, min(900, info.current_h - 110))
        self.mobile = MOBILE_MODE
        self.win = pygame.display.set_mode((0,0),pygame.FULLSCREEN) if IS_ANDROID else pygame.display.set_mode((int(h * CW / CH), h), pygame.RESIZABLE)
        self.touch_gesture=None
        self.touch_pos=(0,0)
        self.keyboard_target=None
        self.suspended=False
        self.last_autosave=0
        self.progress_path=data_directory() / 'night_signal_progress.json'
        self.resume_available=self.mobile and self.progress_path.exists()
        F1 = pygame.font.Font(None, 15)
        F2 = pygame.font.Font(None, 19)
        F3 = pygame.font.Font(None, 40)
        self.snd_ok = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(SR, -16, 1, 512)
            m = pygame.mixer.get_init()
            if m and m[1] == -16:
                build_sounds(m[2])
                self.snd_ok = True
        except Exception:
            self.snd_ok = False
        self.canvas = pygame.Surface((CW, CH), pygame.SRCALPHA)
        self.S = pygame.Surface((SW, SH))
        self.scan = pygame.Surface((SW, SH), pygame.SRCALPHA)
        for y in range(0, SH, 2):
            pygame.draw.line(self.scan, (0, 0, 0, 18), (0, y), (SW, y))
        self.vig = pygame.Surface((SW, SH), pygame.SRCALPHA)
        for k in range(16):
            pygame.draw.rect(self.vig, (0, 0, 0, int(110 * (1 - k / 16.0) ** 2)), (k, k, SW - 2 * k, SH - 2 * k), 1)
        self.clock = pygame.time.Clock()
        self.running = True
        self.now = 0.0
        self.muted = False
        self.tts_on = not IS_ANDROID
        self.tts = None
        self.scare_low = False
        self.hum = None
        self.bgkey = None
        self.ox = self.oy = 0
        self.sc = 1.0
        self.mn = (0.0, 0.0)
        self.m = (-99, -99)
        self.down = False
        self.press_seen = False
        self.btns = []
        self.navb = []
        self.clip = None
        self.scroll = 0.0
        self.maxscr = 0
        self.cap = ('', TXT, 0)
        self.toast_t = ('', 0)
        self.glitch = 0.0
        self.static = 0.0
        self.click_fx = None
        self.last_tn = -1
        self.case = None
        self.desktop = None
        self.pip_open=False
        self.pip_page=0
        self.pip_buttons=[]
        self.pip_touch=None
        self.pip_mouse=False
        self.guide = False
        self.difficulty = 'Beginner'
        self.laptop_browser = False
        self.desk_buttons = []
        self.search_text = ''
        self.profile = None
        self.desk_scroll = 0
        self.note_path = data_directory() / 'night_signal_notes.json'
        try:
            self.notebooks = json.loads(self.note_path.read_text())
            if not isinstance(self.notebooks, dict): self.notebooks = {}
        except (OSError, ValueError):
            self.notebooks = {}
        self.note_key = ''
        self.note_status = 'Saved locally'
        self.hack = None
        self.scare = None
        self.incoming = None
        self.banner = None
        self.dead = None
        self.level = 1
        self.score = 0
        self.hist = []
        self.scr = 'title'
        self.sub = {}
        self.sub_t = 0.0
        self.trans = 0.0
        self.D = {'secrets':self.d_secrets, 'msgsearch':self.d_msgsearch, 'audio':self.d_audio, 'difficulty': self.d_difficulty, 'about': self.d_about, 'title': self.d_title, 'howto': self.d_howto, 'brief': self.d_brief, 'home': self.d_home, 'msg': self.d_msg,
                  'call': self.d_call, 'foot': self.d_foot, 'print': self.d_print, 'insp': self.d_insp, 'intr': self.d_intr,
                  'notes': self.d_notes, 'evid': self.d_evid, 'accuse': self.d_accuse, 'set': self.d_set,
                  'privacy': self.d_privacy, 'photos': self.d_photos, 'device': self.d_device, 'solved': self.d_solved, 'final': self.d_final, 'dead': self.d_dead}

    # ---------------- audio / captions
    def snd(self, name, vol=1.0):
        if self.snd_ok and not self.muted and name in SND:
            try:
                ch = SND[name].play()
                if ch:
                    ch.set_volume(vol)
            except Exception:
                pass

    def set_mute(self, m):
        self.muted = m
        if self.snd_ok:
            try:
                if m:
                    pygame.mixer.stop()
                    if self.tts and self.tts.poll() is None:
                        self.tts.terminate()
                    self.hum = None
                else:
                    self.hum = SND['hum'].play(-1)
                    if self.hum:
                        self.hum.set_volume(.5)
            except Exception:
                pass

    def speak(self, text):
        if IS_ANDROID or self.muted or not self.tts_on:
            return
        try:
            if self.tts and self.tts.poll() is None:
                self.tts.terminate()
        except Exception:
            pass
        txt = ''.join(ch for ch in text if ch.isalnum() or ch in " .,'!?")[:160].lstrip(" .,'!?-")
        if not txt:
            return
        cmd, kw = None, {}
        if sys.platform == 'darwin' and shutil.which('say'):
            cmd = ['say', '-r', '130', txt]
        elif sys.platform.startswith('win'):
            cmd = ['powershell', '-NoProfile', '-Command',
                   "Add-Type -AssemblyName System.Speech;$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;$s.Rate=-2;$s.Speak('%s')" % txt.replace("'", '')]
            kw = {'creationflags': 0x08000000}
        elif shutil.which('espeak'):
            cmd = ['espeak', '-s', '125', txt]
        if cmd:
            try:
                self.tts = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)
            except Exception:
                self.tts = None

    def say(self, text, col=TXT, voice=False, whisper=False, dur=4.0):
        self.cap = (text, col, self.now + dur)
        if whisper:
            self.snd('whisper')
        if voice:
            self.speak(text)

    def toast(self, text):
        self.toast_t = (text, self.now + 3.0)

    # ---------------- navigation
    def go(self, scr, push=True, **sub):
        if push and self.scr != 'title':
            self.hist.append((self.scr, self.sub))
        self.scr, self.sub = scr, sub
        self.sync_keyboard()
        self.scroll = 0.0
        self.sub_t = self.trans = self.now
        self.snd('click')

    def back(self):
        if self.scr == 'device':
            if self.sub.get('tab', 'home') != 'home': self.sub['tab'] = 'home'; self.scroll = 0
            else: self.return_drawer()
            return
        if self.hack or self.scr in ('title', 'brief', 'dead', 'solved', 'final'):
            return
        if self.hist:
            self.scr, self.sub = self.hist.pop()
            self.scroll = 0.0
            self.sub_t = self.trans = self.now
            self.snd('back')
        elif self.scr != 'home':
            self.go('home', push=False)

    def home(self):
        if self.scr == 'device':
            self.sub['tab'] = 'home'; self.scroll = 0
            return
        if self.hack or self.scr in ('title', 'brief', 'dead', 'solved', 'final'):
            return
        self.hist = []
        if self.scr != 'home':
            self.go('home', push=False)

    # ---------------- game flow
    def new_game(self):
        self.level, self.score = 1, 0
        self.start_case()

    def start_case(self):
        self.pip_open=False
        self.guide = False
        seed = random.randrange(10 ** 6)
        for attempt in range(500):
            try:
                c = make_case(self.level, random.Random(seed + attempt))
                if c['scenario'] in getattr(self, 'played', set()):
                    continue
            except ValueError:
                continue
            if not validate(c):
                break
        else:
            raise RuntimeError('could not generate a valid case')
        self.case = c
        if self.difficulty == 'Experienced': self.setup_experienced()
        self.desktop = None
        self.note_key = '%s / %s / %s' % (c['venue'], c['victim'], c['T'])
        self.notebooks.setdefault(self.note_key, '')
        self.played = getattr(self, 'played', set()) | {c['scenario']}
        self.query = ''
        for e in c['ev']:
            if e['anchor'] and e['anchor'][0] == 'file':
                e['found'] = True
        self.marks = [0] * len(c['sus'])
        self.foot = dict(cam='Corridor', t=0.0, play=False, speed=1)
        self.acc = dict(s=None, ev=[], stage=0, msg='')
        self.chances = {'Beginner':5, 'Intermediate':3, 'Experienced':2}[self.difficulty]
        self.esel = []
        self.emsg = ''
        self.links = set()
        self.hacks_left = 0 if self.difficulty == 'Beginner' else c['hacks'] + (self.difficulty == 'Experienced')
        self.hack_t = random.uniform(40, 75)
        self.ev_t = random.uniform(30, 55)
        self.case_time = 0.0
        self.last_scare = -999
        self.hack = self.incoming = self.banner = self.scare = self.dead = None
        self.hist = []
        self.go('brief', push=False)
        if self.snd_ok and not self.muted and not self.hum:
            self.set_mute(False)

    def find(self, eid):
        e = self.case['ev'][eid]
        if not e['found']:
            e['found'] = True
            self.snd('good')
            is_filed=any(eid in entries.values() for entries in self.case.get('artifacts',{}).values())
            self.toast(('SAVED TO ACCUSATION FOLDER: ' if is_filed else 'NEW EVIDENCE: ') + e['title'])

    def connect(self):
        c = self.case
        a, b = (c['ev'][i] for i in self.esel)
        if a['subj'] is None or b['subj'] is None or a['subj'] != b['subj']:
            self.emsg = 'No clear connection between these two.'
            self.snd('bad')
            return
        key = tuple(sorted(self.esel))
        if key in self.links:
            self.emsg = 'You already made this connection.'
            return
        self.links.add(key)
        kind, txt = 'ctx', 'Compare the dates, limitations and identifiers in both sources. Shared names alone do not prove guilt.'
        c['ev'].append(dict(id=len(c['ev']), title='Link: %s + %s' % (a['title'][:14], b['title'][:14]), text=txt, src='LINK',
                            subj=a['subj'], kind=kind, anchor=('link', None), found=True))
        self.emsg = 'Connection made! Added to your evidence.'
        self.esel = []
        self.snd('good')

    def submit_accuse(self):
        c, a = self.case, self.acc
        good = a['ev']
        if proof_valid(c, a['s'], a['ev'], a.get('when'), a.get('method')):
            self.score += 100 * self.level + 25 * len(good) + 20 * self.chances
            self.go('solved', push=False, n=len(good))
            self.snd('good')
            self.say('Case closed. The line goes quiet... for now.', ACC)
            return
        if len(a['ev']) != 3 or a.get('when') is None or a.get('method') is None:
            a['msg'] = 'Complete your explanation and choose three exhibits.'
            a['stage'] = 0
            return
        if not all(c['ev'][i]['found'] for i in (c['incident_ev'], c['clock_ev'])):
            a['msg'] = 'Read the scene log and clock message first.'
            a['stage'] = 0
            return
        self.chances -= 1
        if self.chances <= 0:
            self.dead = dict(t0=self.now, name=c['sus'][a['s']]['name'])
            self.go('dead', push=False)
            return
        a['msg'] = 'Your reconstruction is unsupported. %d chances left.' % self.chances
        a['stage'] = 0
        a['ev'] = []
        self.snd('bad')
        self.glitch = .5
        self.say('That is not what happened...', RED, voice=True, whisper=True)

    # ---------------- events: scares, hacks, calls
    def scare_gap(self):
        return (80, 140) if self.scare_low else (45, 90)

    def random_event(self):
        c = self.case
        self.ev_t = random.uniform(*self.scare_gap())
        r = random.random()
        if r < .35:
            th = c['threads'].setdefault('Unknown', dict(key='Unknown', role='???', sus=None, msgs=[], unread=True))
            txt = random.choice(CREEPY)
            th['msgs'].append(dict(d=0, t=fmt(self.case_time / 10 + 200), x=txt, ev=None))
            th['unread'] = True
            self.banner = dict(t0=self.now, text='Unknown: ' + txt)
            self.snd('glitch')
        elif r < .55:
            self.incoming = dict(t0=self.now, state='ring', contact=random.randrange(len(c['tips'])))
        elif r < .8 or self.now - self.last_scare < 100 or self.case_time < 60:
            self.glitch, self.static = 1.0, .7
            self.snd('static')
            self.say(random.choice(VOICE), RED, voice=True, whisper=True)
        else:
            self.last_scare = self.now
            self.scare = dict(t0=self.now)
            self.snd('scare')
            self.say('BEHIND YOU', RED, dur=2)

    def start_hack(self):
        self.hacks_left -= 1
        self.hack = dict(kind=random.choice(['simon', 'nodes', 'virus']), phase='warn', t0=self.now, st={})
        self.glitch, self.static = 1.6, 1.0
        self.snd('static')
        self.say('SYSTEM BREACH: someone is inside your phone.', RED, voice=True, whisper=True)
        self.incoming = self.banner = None

    def hack_begin(self):
        h = self.hack
        h['phase'] = 'play'
        h['t0'] = self.now
        st = h['st'] = {}
        if h['kind'] == 'simon':
            st['seq'] = [random.randrange(4) for _ in range(3 + min(self.level, 4) + (self.difficulty == 'Experienced'))]
            st['inp'] = []
            st['show'] = self.now + .6
            st['msg'] = 'Watch...'
        elif h['kind'] == 'nodes':
            self.hack_nodes()
        else:
            self.hack_virus()

    def hack_nodes(self):
        st = self.hack['st']
        pts = []
        while len(pts) < 6:
            p = (random.randint(14, SW - 44), random.randint(90, 230))
            if all(abs(p[0] - q[0]) > 34 or abs(p[1] - q[1]) > 28 for q in pts):
                pts.append(p)
        st['pts'], st['next'], st['end'], st['msg'] = pts, 0, self.now + 18, 'Tap 1 to 6 in order.'

    def hack_virus(self):
        st = self.hack['st']
        st['bugs'] = [[random.uniform(20, SW - 40), random.uniform(90, 230), random.uniform(-45, 45), random.uniform(-45, 45)] for _ in range(5)]
        st['end'] = self.now + 20
        st['msg'] = 'Purge all the red bugs!'

    def hack_done(self):
        self.hack['phase'] = 'done'
        self.hack['t0'] = self.now
        self.snd('good')
        self.say('Access restored.', ACC)
        self.hack_t = random.uniform(60, 100)

    # ---------------- input
    def to_canvas(self, pos):
        return ((pos[0] - self.ox) / self.sc, (pos[1] - self.oy) / getattr(self, "sc_y", self.sc))

    def input_target(self):
        if self.desktop is None and self.scr=='msgsearch':return 'conversation'
        if self.desktop == 'notebook': return 'note'
        if self.desktop == 'laptop' and self.laptop_browser and self.profile is None: return 'search'
        return None

    def sync_keyboard(self):
        target=self.input_target()
        if not self.mobile or target == self.keyboard_target:return
        self.keyboard_target=target
        if target:
            pygame.key.set_text_input_rect(pygame.Rect(0,0,*self.win.get_size()))
            pygame.key.start_text_input()
        else:pygame.key.stop_text_input()

    def insert_mobile_text(self,text):
        target=self.input_target()
        if target=='conversation':
            self.conversation_query=(getattr(self,'conversation_query','')+text.replace('\n',''))[:80];self.scroll=0
        elif target=='note':
            self.notebooks[self.note_key]+=text
            self.save_notebook();self.desk_scroll=10**8
        elif target=='search':
            self.search_text=(self.search_text+text.replace('\n',''))[:60]
            self.desk_scroll=0

    def mobile_event(self,e):
        # Return True when handled. SDL's synthesized mouse events are ignored
        # because finger taps are committed once, on release after swipe detection.
        if getattr(e,'touch',False) and e.type in (pygame.MOUSEBUTTONDOWN,pygame.MOUSEBUTTONUP,pygame.MOUSEMOTION):return True
        if e.type==pygame.TEXTINPUT:
            if self.mobile:self.insert_mobile_text(e.text);return True
            return False
        if e.type in (pygame.APP_WILLENTERBACKGROUND,pygame.APP_DIDENTERBACKGROUND):
            self.suspended=True;self.save_progress();self.save_notebook()
            self.touch_gesture=None;self.down=False
            if self.snd_ok:pygame.mixer.pause()
            pygame.key.stop_text_input();self.keyboard_target=None
            return True
        if e.type in (pygame.APP_DIDENTERFOREGROUND,):
            self.suspended=False;self.clock.tick();self.sync_keyboard()
            if self.snd_ok and not self.muted:pygame.mixer.unpause()
            return True
        if e.type==pygame.KEYDOWN and e.key==getattr(pygame,'K_AC_BACK',1073742094):
            if self.keyboard_target:
                pygame.key.stop_text_input();self.keyboard_target=None
            elif self.desktop is not None:
                if self.desktop=='desk':self.desktop=None
                else:self.enter_desk('desk')
            elif self.scr=='title':self.save_progress();self.running=False
            elif self.scr in ('brief','solved','dead','final'):self.go('title',push=False)
            else:self.back()
            self.render();return True
        if e.type not in (pygame.FINGERDOWN,pygame.FINGERMOTION,pygame.FINGERUP):return False
        self.mobile=True
        W,H=pygame.display.get_surface().get_size();pos=(e.x*W,e.y*H)
        self.touch_pos=pos
        if e.type==pygame.FINGERDOWN:
            if self.touch_gesture is None:
                canvas=self.to_canvas(pos) if self.desktop is None else None
                seek=self.desktop is None and self.scr=='foot' and 160<=canvas[1]-SY<=194
                self.touch_gesture=dict(id=e.finger_id,start=pos,last=pos,drag=False,seek=seek)
                if self.desktop=='board' and not self.case['expert']['picker']:
                    point=((pos[0]-self.desk_x)/self.desk_scale,(pos[1]-self.desk_y)/self.desk_scale)
                    if 78<=point[1]<=288:
                        self.handle_desk(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=pos))
                        self.touch_gesture['board']=True
            return True
        gesture=self.touch_gesture
        if gesture is None or gesture['id']!=e.finger_id:return True
        if e.type==pygame.FINGERMOTION:
            distance=math.hypot(pos[0]-gesture['start'][0],pos[1]-gesture['start'][1])
            if distance>max(8,min(W,H)*.025):gesture['drag']=True
            if gesture.get('board'):
                if getattr(self,'board_drag',None) is not None:self.board_place(((pos[0]-self.desk_x)/self.desk_scale,(pos[1]-self.desk_y)/self.desk_scale))
            elif gesture['seek']:
                x=self.to_canvas(pos)[0]-SX
                self.foot.update(t=clamp((x-8)/(SW-16)*TMAX,0,TMAX),play=False)
            elif gesture['drag']:
                delta=pos[1]-gesture['last'][1]
                if self.desktop is not None:
                    self.desk_scroll=clamp(self.desk_scroll-delta/self.desk_scale,0,self.desk_max)
                else:self.scroll=clamp(self.scroll-delta/self.sc_y,0,self.maxscr)
            gesture['last']=pos
            return True
        self.touch_gesture=None
        if gesture.get('board'):
            self.board_drag=None;self.render();return True
        if gesture['seek']:
            x=self.to_canvas(pos)[0]-SX
            self.foot.update(t=clamp((x-8)/(SW-16)*TMAX,0,TMAX),play=False)
        elif not gesture['drag']:
            if self.desktop is not None:
                self.handle_desk(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=pos))
            else:self.click(pos)
        self.sync_keyboard();self.render()
        return True

    def save_progress(self):
        if not self.mobile or not self.case:return
        keys=('case','level','score','marks','foot','acc','chances','played','links','case_time','note_key','difficulty')
        state={key:getattr(self,key) for key in keys}
        state['screen']=self.scr if self.scr in ('brief','solved','final') else 'home'
        try:
            atomic_json(self.progress_path,{'version':1,'state':pack_state(state)})
            self.resume_available=True
        except OSError:self.toast('Could not save progress')

    def resume_progress(self):
        try:
            data=json.loads(self.progress_path.read_text())
            if data.get('version')!=1:raise ValueError('save version')
            state=unpack_state(data['state'])
            if validate(state['case']):raise ValueError('invalid case')
        except (OSError,ValueError,KeyError,TypeError):
            self.toast('Saved progress could not be opened');return
        self.start_case()
        for key,value in state.items():
            if key!='screen':setattr(self,key,value)
        if self.difficulty=='Experienced' and 'expert' not in self.case:self.setup_experienced()
        self.desktop=None;self.guide=False;self.hist=[]
        if 'expert' in self.case:self.case['expert'].update(next_event=self.now+random.uniform(70,120),wake_until=0,notice_until=0)
        self.go(state['screen'],push=False)

    def d_privacy(self):
        self.tile_back();self.header('PRIVACY / OFFLINE GAME')
        content=('Night Signal runs offline. The game does not send your notebook, searches, device information or progress to a server. There are no ads or analytics in this build.\n\n'
                 'All suspects, phone messages, cameras and web searches are fictional. The game does not access your real contacts, calls, camera, microphone or location.\n\n'
                 'Notes and mobile progress are stored locally in app-private storage. Android backup is disabled in the build configuration. Clearing app storage or uninstalling removes them.\n\n'
                 'Google Play may independently process store, purchase or diagnostic information under its own policies. The developer contact is listed on the store page.')
        def draw(y,w):return self.para(content,6,y,w-8,TXT)-y
        self.scrollv((0,34,SW,218),draw)
        self.btn((8,260,182,22),'BACK',self.back)

    def process_event(self, e):
        if self.pip_event(e):return
        if self.mobile_event(e):return
        # Rebuild targets after each input, not only after an entire queued batch.
        # A click opening a desk/app can be followed by another input in that batch.
        resize_types = (pygame.VIDEORESIZE, pygame.WINDOWSIZECHANGED)
        if e.type in resize_types:
            self.render()
            return
        if e.type == pygame.WINDOWFOCUSLOST:
            self.press_seen = False
            self.down = False
            return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.press_seen = True
            self.handle(e)
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            had_press = self.press_seen
            self.press_seen = False
            self.down = False
            if not had_press:
                # Some window managers consume the press when focusing a window.
                # The release still completes that single click; never run both.
                if self.desktop is None:
                    self.click(e.pos)
                else:
                    self.handle_desk(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=e.pos))
            self.handle(e)
        else:
            self.handle(e)
        self.sync_keyboard()
        if self.running and e.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP,
                                      pygame.MOUSEWHEEL, pygame.KEYDOWN, pygame.WINDOWFOCUSGAINED):
            self.render()

    def handle(self, e):
        if self.desktop is not None:
            self.handle_desk(e)
            return
        if e.type == pygame.QUIT:
            self.running = False
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.down = True
            self.click(e.pos)
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.down = False
        elif e.type == pygame.MOUSEWHEEL:
            if self.maxscr > 0:
                self.scroll = clamp(self.scroll - e.y * 18, 0, self.maxscr)
        elif e.type == pygame.KEYDOWN:
            if self.scr=='msgsearch' and e.key!=pygame.K_ESCAPE:
                if e.key==pygame.K_BACKSPACE:self.conversation_query=self.conversation_query[:-1]
                elif not self.mobile and e.unicode.isprintable():self.conversation_query=(self.conversation_query+e.unicode)[:80]
                self.scroll=0;return
            if e.key == pygame.K_ESCAPE:
                if self.scr == 'title':
                    self.running = False
                else:
                    self.back()
            elif e.key == pygame.K_m:
                self.set_mute(not self.muted)

    def click(self, pos):
        mc = self.to_canvas(pos)
        if self.scare:
            return
        for r, fn in self.navb:
            if r.collidepoint(mc):
                self.click_fx = ((mc[0] - SX, mc[1] - SY), self.now)
                fn()
                return
        m = (mc[0] - SX, mc[1] - SY)
        for r, fn in reversed(self.btns):
            if r.collidepoint(m):
                self.click_fx = (m, self.now)
                self.snd('click')
                fn()
                return

    # ---------------- update
    def update(self, dt):
        if self.pip_open:return
        if self.case and self.difficulty == 'Experienced': self.update_desk_events()
        if self.desktop is not None: return
        self.glitch = max(0, self.glitch - dt)
        self.static = max(0, self.static - dt * .8)
        if self.scr in APPS and self.case:
            idle = not (self.hack or self.scare or self.incoming or self.guide or self.scr == 'device')
            if idle:
                self.case_time += dt
                self.ev_t -= dt
                if self.ev_t <= 0:
                    self.random_event()
                if self.hacks_left > 0:
                    self.hack_t -= dt
                    if self.hack_t <= 0:
                        self.start_hack()
            if self.scr == 'foot' and self.foot['play'] and not self.hack:
                f = self.foot
                f['t'] += dt * 2.0 * f['speed']
                if f['t'] >= TMAX:
                    f['t'], f['play'] = TMAX, False
        if self.scare and self.now - self.scare['t0'] > .75:
            self.scare = None
        if self.banner and self.now - self.banner['t0'] > 4:
            self.banner = None
        inc = self.incoming
        if inc:
            if inc['state'] == 'ring' and self.now - inc['t0'] > 10:
                self.incoming = None
            elif inc['state'] == 'ring' and int((self.now - inc['t0']) * 1.0) != inc.get('last', -1):
                inc['last'] = int(self.now - inc['t0'])
                self.snd('ring', .6)
            elif inc['state'] == 'talk' and self.now - inc['t0'] > 9:
                self.incoming = None
                self.glitch = .8
                if random.random() < .25 and self.now - self.last_scare > 100:
                    self.last_scare = self.now
                    self.scare = dict(t0=self.now)
                    self.snd('scare')
        h = self.hack
        if h:
            if h['phase'] == 'warn' and self.now - h['t0'] > 1.8:
                h['phase'] = 'intro'
            elif h['phase'] == 'done' and self.now - h['t0'] > 1.4:
                self.hack = None
            elif h['phase'] == 'play':
                st = h['st']
                if h['kind'] == 'simon' and 'show' in st and st['show'] is not None and self.now >= st['show']:
                    k = st.get('i', 0)
                    if k < len(st['seq']):
                        st['lit'] = (st['seq'][k], self.now + .35)
                        self.snd('p%d' % st['seq'][k])
                        st['i'] = k + 1
                        st['show'] = self.now + .65
                    else:
                        st['show'] = None
                        st['msg'] = 'Your turn. Repeat the sequence.'
                elif h['kind'] == 'nodes' and self.now > st['end']:
                    self.snd('bad')
                    self.hack_nodes()
                    st['msg'] = 'Too slow. Try again.'
                elif h['kind'] == 'virus':
                    for b in st['bugs']:
                        b[0] += b[2] * dt
                        b[1] += b[3] * dt
                        if b[0] < 6 or b[0] > SW - 24:
                            b[2] = -b[2]
                        if b[1] < 90 or b[1] > 250:
                            b[3] = -b[3]
                    if self.now > st['end']:
                        self.snd('bad')
                        self.hack_virus()
                        st['msg'] = 'They multiplied. Try again.'

    # ---------------- drawing primitives
    def text(self, s, x, y, col=TXT, f=None, center=False, right=False):
        f = f or F1
        im = f.render(s, True, col)
        if center:
            x -= im.get_width() // 2
        elif right:
            x -= im.get_width()
        self.S.blit(im, (x, y))
        return im.get_width()

    def para(self, s, x, y, w, col=TXT, f=None, gap=1):
        f = f or F1
        for ln in wrap(s, f, w):
            self.text(ln, x, y, col, f)
            y += f.get_linesize() + gap
        return y

    def para_typed(self, s, x, y, w, t0, col=TXT):
        n = int((self.now - t0) * 45)
        if n != self.last_tn and n % 4 == 0 and n < len(s):
            self.snd('type', .4)
        self.last_tn = n
        for ln in wrap(s, F1, w):
            self.text(ln[:max(0, n)], x, y, col)
            n -= len(ln) + 1
            y += F1.get_linesize() + 1
        return y, n > 0

    def btn(self, r, label, fn, col=ACC, align='c', en=True, sel=False, f=None, bg=None):
        r = pygame.Rect(r)
        S = self.S
        f = f or F1
        vis = r if self.clip is None else r.clip(self.clip)
        hov = en and vis.w > 0 and vis.collidepoint(self.m)
        dn = hov and self.down
        fill = bg or ((34, 78, 70) if sel else PANEL2)
        if hov:
            fill = tuple(min(255, q + 18) for q in fill)
        rr = r
        pygame.draw.rect(S, fill, rr, border_radius=3)
        pygame.draw.rect(S, col if en else LINE, rr, 1, border_radius=3)
        if hov:
            pygame.draw.rect(S, WHITE, rr.inflate(2, 2), 1, border_radius=4)
        if label:
            im = f.render(fit(label, f, r.w - 8), True, TXT if en else DIM)
            x = rr.x + (rr.w - im.get_width()) // 2 if align == 'c' else rr.x + 4
            S.blit(im, (x, rr.y + (rr.h - im.get_height()) // 2))
        if en and vis.w > 0 and vis.h > 0:
            self.btns.append((vis, fn))
        return r

    def scrollv(self, r, draw, stick=False):
        r = pygame.Rect(r)
        S = self.S
        S.set_clip(r)
        self.clip = r
        h = draw(r.y - int(self.scroll), r.w - 16)
        S.set_clip(None)
        self.clip = None
        mx = max(0, h - r.h)
        self.maxscr = mx
        if stick:
            self.scroll = mx
        self.scroll = clamp(self.scroll, 0, mx)
        if mx > 0:
            gx = r.right - 13
            self.btn((gx, r.y, 12, 14), '', lambda: self.nudge(-36))
            self.btn((gx, r.bottom - 14, 12, 14), '', lambda: self.nudge(36))
            pygame.draw.polygon(S, TXT, [(gx + 6, r.y + 4), (gx + 3, r.y + 10), (gx + 9, r.y + 10)])
            pygame.draw.polygon(S, TXT, [(gx + 6, r.bottom - 4), (gx + 3, r.bottom - 10), (gx + 9, r.bottom - 10)])
            th = max(10, int((r.h - 32) * r.h / (r.h + mx)))
            ty = r.y + 16 + int((r.h - 32 - th) * self.scroll / mx)
            pygame.draw.rect(S, LINE, (gx + 5, r.y + 16, 2, r.h - 32))
            pygame.draw.rect(S, ACC, (gx + 4, ty, 4, th))

    def nudge(self, d):
        self.scroll = clamp(self.scroll + d, 0, self.maxscr)

    def header(self, title):
        pygame.draw.rect(self.S, PANEL, (0, 12, SW, 17))
        pygame.draw.line(self.S, LINE, (0, 29), (SW, 29))
        self.text(title, 6, 14, ACC, F2)

    def status_bar(self):
        S = self.S
        pygame.draw.rect(S, (4, 6, 8), (0, 0, SW, 12))
        mins = int(self.case_time / 10) if self.case else 0
        t = '%02d:%02d' % ((23 + (mins + 0) // 60) % 24, mins % 60) if int(self.now) % 41 else '03:33'
        self.text(t, 4, 1, DIM)
        blocked = bool(self.hack and self.hack['phase'] != 'done')
        for k in range(4):
            pygame.draw.rect(S, RED if blocked else (DIM if k > 2 else TXT), (SW - 46 + k * 4, 9 - k * 2, 3, 2 + k * 2))
        pygame.draw.rect(S, DIM, (SW - 24, 3, 16, 7), 1)
        pygame.draw.rect(S, ACC if not self.muted else AMB, (SW - 23, 4, 11, 5))

    def tile_back(self):
        S = self.S
        S.fill((10, 14, 18))

    # ---------------- screens
    def d_title(self):
        S = self.S
        t = self.now
        S.fill((4, 6, 9))
        for k in range(14):
            x = (k * 37 + int(t * (4 + k % 3))) % SW
            pygame.draw.line(S, (12, 20, 24), (x, 0), (x, SH))
        pygame.draw.circle(S, (16, 24, 28), (int(120 + self.mn[0] * 8), 70), 38)
        pygame.draw.circle(S, (4, 6, 9), (int(132 + self.mn[0] * 8), 64), 36)
        sh = 1 if int(t * 7) % 17 else 4
        for dx, col in ((-sh, (90, 20, 30)), (sh, (20, 80, 90)), (0, TXT)):
            self.text('NIGHT', 99 + dx, 44, col, F3, center=True)
            self.text('SIGNAL', 99 + dx, 76, col, F3, center=True)
        self.text('a detective story told through a phone', 99, 112, DIM, center=True)
        if self.resume_available:
            self.btn((30,128,138,20),'CONTINUE',self.resume_progress)
        self.btn((30, 151, 138, 22), 'NEW GAME', self.new_game, f=F2)
        self.btn((12, 177, 174, 22), 'DIFFICULTY: '+self.difficulty, lambda:self.go('difficulty',push=False))
        self.btn((30, 203, 138, 22), 'TUTORIAL', self.start_title_tutorial)
        self.btn((12, 229, 84, 22), 'ABOUT GAME', lambda:self.go('about',push=False))
        self.btn((102, 229, 84, 22), 'QUIT', lambda:setattr(self,'running',False),col=RED)
        self.text('Read. Compare. Reconstruct.',99,263,DIM,center=True)

    def d_difficulty(self):
        self.tile_back();self.header('DIFFICULTY')
        modes=[('Beginner','5 chances. No hacking interruptions. Best for learning to read the evidence.'),
               ('Intermediate','3 chances. Standard hacking puzzles and interruptions.'),
               ('Experienced','2 chances. No Pip help. Harder hacks, advanced tools and desk events.')]
        y=36
        for name,description in modes:
            self.btn((8,y,182,23),name,lambda n=name:setattr(self,'difficulty',n),sel=self.difficulty==name)
            self.para(description,9,y+26,180,DIM)
            y+=67
        self.text('Applies when starting a new case.',99,239,AMB,center=True)
        self.btn((20,257,158,22),'BACK TO TITLE',lambda:self.go('title',push=False))

    def d_about(self):
        self.tile_back();self.header('ABOUT THE GAME')
        body=('An atmospheric detective mystery told through fictional phones and a late-night investigation desk. '
              'Solve five cases from hundreds of scenario combinations: disappearances, murders, theft, sabotage and more.\n\n'
              'Read messages, zoom into photographs, inspect scenes and replay security footage. Search public profiles on your laptop, '
              'examine archived suspect phones and question people in the interrogation room. Keep your own notebook.\n\n'
              'Your job is to reconstruct what happened. Compare clock corrections, device changes and travel times. '
              'A fingerprint or suspicious message alone is never enough. Choose the suspect, supporting exhibits, incident time and method.\n\n'
              'Everything is fictional and offline. Contains horror and flashing effects. The tutorial is optional; difficulty changes chances and hacking pressure, while every mode requires reading.')
        self.scrollv((0,35,SW,213),lambda y,w:self.para(body,8,y,w-16,TXT)-y)
        self.btn((20,257,158,22),'BACK TO TITLE',lambda:self.go('title',push=False))

    def open_tutorial(self, origin='home', page=0):
        if self.difficulty != 'Experienced' and self.case and origin != 'title' and page == 0:
            self.guide = True
            self.go('home', push=False)
        else:
            self.go('howto', push=False, origin=origin, page=page)

    def start_bot_demo(self):
        if self.difficulty=='Experienced':return
        if not self.case or self.sub.get('origin') == 'title': self.new_game()
        self.guide = True
        self.go('home', push=False)

    def tutorial_page(self, page):
        self.sub['page'] = page
        self.scroll = 0

    def d_howto(self):
        self.tile_back()
        pages = list(TUTORIAL_PAGES)
        if self.case and self.sub.get('origin', 'title') != 'title':
            c = self.case
            lines = []
            lines = ['Collect observations; there are no automatic suspect comparisons.']
            tip = 'Read the scene log and technician message. Correct the clock, check label-change times in handset messages, and calculate travel opportunity from public entries.'
            pages.append(('Your case checklist', '\n'.join(lines) + '\n\nNext step: ' + tip + '\n\nThis checklist does not choose a suspect for you.'))
        page = clamp(self.sub.get('page', 0), 0, len(pages)-1)
        title, body = pages[page]
        self.header('TUTORIAL %d/%d' % (page+1, len(pages)))
        def draw(y, w):
            return self.para(title+'\n\n'+body, 6, y, w-8, TXT)-y
        self.scrollv((0, 34, SW, 173), draw)
        self.btn((6, 211, 186, 20), 'PIP DISABLED IN EXPERIENCED' if self.difficulty=='Experienced' else 'LEARN WITH PIP', self.start_bot_demo, col=ACC, en=self.difficulty!='Experienced')
        self.btn((6, 238, 90, 19), 'PREV', lambda: self.tutorial_page(page-1), en=page>0)
        self.btn((102, 238, 90, 19), 'NEXT', lambda: self.tutorial_page(page+1), en=page<len(pages)-1)
        origin = self.sub.get('origin', 'title')
        self.btn((6, 261, 186, 20), 'BACK TO TITLE' if origin=='title' else 'RETURN TO CASE', lambda: self.go(origin, push=False), col=ACC)

    def d_brief(self):
        c = self.case
        self.tile_back()
        self.header('CASE %d OF 5' % self.level)
        txt = c['brief']
        y = self.para(txt, 6, 36, 186, TXT)
        self.text('Score: %d' % self.score, 6, y + 4, AMB)
        self.btn((20, 240, 158, 26), 'OPEN CASE FILE', lambda: self.start_play(), f=F2)

    def start_play(self):
        self.go('home', push=False)
        self.say('Case file open. Find the culprit.', ACC)

    def start_title_tutorial(self):
        if self.difficulty=='Experienced':
            self.guide=False;self.pip_open=False
            self.go('howto',push=False,origin='title',page=0);return
        self.new_game()
        self.guide = True
        self.go('home', push=False)

    def d_home(self):
        c, S = self.case, self.S
        for y in range(0, SH, 6):
            pygame.draw.rect(S, (8 + y // 28, 12 + y // 22, 18 + y // 18), (0, y, SW, 6))
        mx = self.mn[0]
        pygame.draw.circle(S, (30, 44, 52), (int(158 + mx * 7), 250), 24)
        pygame.draw.circle(S, (10, 16, 22), (int(166 + mx * 7), 246), 22)
        pygame.draw.rect(S, (14, 22, 28), (6, 16, SW - 12, 46), border_radius=4)
        pygame.draw.rect(S, LINE, (6, 16, SW - 12, 46), 1, border_radius=4)
        self.text('CASE %d/5  %s' % (self.level, c['venue']), 12, 20, AMB)
        self.text('Victim: ' + c['victim'], 12, 32, TXT)
        self.text('Incident time: verify logger clock', 12, 44, DIM)
        self.btn((56, 255, 136, 19), 'CASE CHECKLIST', lambda: self.open_tutorial('home', len(TUTORIAL_PAGES)))
        apps = [('msg', 'Messages'), ('call', 'Calls'), ('foot', 'CCTV'), ('print', 'Prints'), ('insp', 'Inspect'),
                ('intr', 'Interview'), ('notes', 'Notes'), ('evid', 'Evidence'), ('photos', 'Photos'), ('accuse', 'Accuse'), ('set', 'Settings')]
        for i, (k, lab) in enumerate(apps):
            x, y = 5 + (i % 4) * 47, 72 + (i // 4) * 51
            self.btn((x, y, 45, 48), '', lambda k=k: self.open_app(k), bg=(14, 20, 26))
            draw_icon(S, k, pygame.Rect(x + 9, y + 3, 26, 26))
            self.text(fit(lab,F1,44), x + 22, y + 34, TXT, center=True)
            badge = 0
            if k == 'msg':
                badge = sum(1 for t in c['threads'].values() if t['unread'])
            elif k == 'call':
                badge = sum(1 for q in c['calls'] if not q['heard'])
            elif k == 'evid':
                badge = sum(1 for e in c['ev'] if e['found'])
            if badge:
                pygame.draw.circle(S, RED if k != 'evid' else (40, 120, 110), (x + 40, y + 6), 6)
                self.text(str(min(badge, 99)), x + 40, y + 2, WHITE, center=True)

    def open_app(self, k):
        if k == 'foot':
            self.go('foot')
        elif k == 'insp':
            self.go('insp', room=self.case['R'], sel=None)
        elif k == 'notes' or k == 'evid':
            self.esel, self.emsg = [], ''
            self.go(k)
        else:
            self.go(k)

    # -- messages
    def open_thread(self, k):
        self.case['threads'][k]['unread'] = False
        self.go('msg', th=k)

    def d_msg(self):
        c = self.case
        self.tile_back()
        k = self.sub.get('th')
        if k is None:
            self.header('MESSAGES')
            if self.difficulty=='Experienced':self.btn((6,30,186,18),'SEARCH CONVERSATIONS',lambda:self.open_message_search(None))
            else:self.text("Recovered from %s's phone" % c['vfirst'], 6, 32, DIM)

            def draw(y, w):
                y0 = y
                for key, t in c['threads'].items():
                    r = pygame.Rect(4, y, w, 30)
                    self.btn(r, '', lambda kk=key: self.open_thread(kk))
                    col = c['sus'][t['sus']]['col'] if t['sus'] is not None else ((120, 120, 130) if key != 'Unknown' else RED)
                    pygame.draw.rect(self.S, col, (r.x + 4, y + 5, 20, 20))
                    self.text(key[0], r.x + 14, y + 10, BG, center=True)
                    self.text(fit(key, F1, w - 40), r.x + 28, y + 3, TXT)
                    last = t['msgs'][-1]['x'] if t['msgs'] else ''
                    self.text(fit(t['role'] + ': ' + last, F1, w - 40), r.x + 28, y + 15, DIM)
                    if t['unread']:
                        pygame.draw.circle(self.S, RED, (r.right - 8, y + 8), 3)
                    y += 33
                return y - y0
            self.scrollv((0, 50, SW, SH - 50), draw)
            return
        th = c['threads'][k]
        self.header(fit(k, F2, 180))
        msgs = th['msgs']
        n = min(len(msgs), int((self.now - self.sub_t) / .3) + 1)

        def draw(y, w):
            y0 = y
            for m in msgs[:n]:
                if m['ev'] is not None:
                    self.find(m['ev'])
                lines = wrap(m['x'], F1, w - 50)
                bw = max(max(F1.size(l)[0] for l in lines), F1.size(m['t'])[0]) + 10
                bh = len(lines) * 11 + 15
                bx = 6 if m['d'] == 0 else 6 + w - bw
                pygame.draw.rect(self.S, PANEL2 if m['d'] == 0 else (24, 66, 60), (bx, y, bw, bh), border_radius=4)
                for j, ln in enumerate(lines):
                    self.text(ln, bx + 5, y + 3 + j * 11, TXT)
                self.text(m['t'], bx + 5, y + bh - 11, DIM)
                y += bh + 5
            if n < len(msgs):
                for j in range(3):
                    pygame.draw.circle(self.S, ACC if int(self.now * 6) % 3 == j else DIM, (14 + j * 8, y + 5), 2)
                y += 14
            return y - y0
        self.scrollv((0, 32, SW, SH - (62 if self.difficulty=='Experienced' else 32)), draw, stick=n < len(msgs))
        if self.difficulty=='Experienced':self.btn((6,258,186,22),'SAVE THREAD FOR BOARD',lambda:self.save_thread_pin(k))

    # -- calls
    def d_call(self):
        c = self.case
        self.tile_back()
        i = self.sub.get('i')
        if i is None:
            self.header('CALLS')
            if self.difficulty=='Experienced':self.btn((6,30,186,18),'AUDIO INVESTIGATION',lambda:self.go('audio'))
            else:self.text('Call history and recordings', 6, 32, DIM)

            def draw(y, w):
                y0 = y
                for j, q in enumerate(c['calls']):
                    r = pygame.Rect(4, y, w, 28)
                    self.btn(r, '', lambda jj=j: self.open_call(jj))
                    col = {'IN': ACC, 'OUT': BLUE, 'MISSED': RED}[q['dir']]
                    self.text(q['dir'], r.x + 4, y + 3, col)
                    self.text(fit(q['who'], F1, w - 60), r.x + 36, y + 3, TXT)
                    self.text('%s   %s' % (q['t'], q['dur']), r.x + 36, y + 15, DIM)
                    if not q['heard']:
                        pygame.draw.circle(self.S, RED, (r.right - 8, y + 8), 3)
                    y += 31
                return y - y0
            self.scrollv((0, 50, SW, SH - 50), draw)
            return
        q = c['calls'][i]
        self.header('CALL RECORD')
        self.text(fit(q['who'], F2, 186), 6, 34, TXT, F2)
        self.text('%s   %s   %s' % (q['dir'], q['t'], q['dur']), 6, 50, DIM)
        if q['info']:
            self.text(fit(q['info'], F1, 186), 6, 62, AMB)
        if not self.sub.get('play'):
            self.btn((20, 84, 158, 24), 'PLAY RECORDING', lambda: self.play_call(i), f=F2)
            return
        dt = self.now - self.sub['play']
        if dt < .8:
            self.text('loading recording' + '.' * (int(dt * 6) % 4), 10, 90, ACC)
            pygame.draw.rect(self.S, LINE, (10, 104, 178, 6), 1)
            pygame.draw.rect(self.S, ACC, (11, 105, int(176 * dt / .8), 4))
            return
        if q['ev'] is not None:
            self.find(q['ev'])
        y = 84
        t0 = self.sub['play'] + .8
        for ln in q['lines']:
            y, done = self.para_typed(ln, 8, y, 180, t0, TXT)
            y += 4
            t0 += len(ln) / 45.0 + .3
        self.btn((20, 250, 158, 22), 'PLAY AGAIN', lambda: self.play_call(i))

    def open_call(self, j):
        self.case['calls'][j]['heard'] = True
        self.go('call', i=j)

    def play_call(self, j):
        self.sub['play'] = self.now
        q = self.case['calls'][j]
        self.say(q['lines'][-1].strip('"'), AMB, voice=True)
        self.snd('ring', .5)

    # -- footage
    def set_cam(self, cam):
        self.foot['cam'] = cam

    def d_foot(self):
        c, f, S = self.case, self.foot, self.S
        self.tile_back()
        self.header('SECURITY FOOTAGE')
        for j, cam in enumerate(('Corridor', 'Lobby')):
            self.btn((6 + j * 94, 32, 92, 16), 'CAM %d %s' % (j + 1, cam), lambda cam=cam: self.set_cam(cam), sel=(f['cam'] == cam))
        vr = pygame.Rect(6, 52, SW - 12, 96)
        t = f['t']
        draw_cam(S, vr, f['cam'], t, c, self.now, self.glitch > 0 or int(self.now * 6) % 23 == 0 and f['play'])
        segs = c['cams'][f['cam']]
        for g in segs:
            if g['ev'] is not None and g['t0'] <= t <= g['t1']:
                self.find(g['ev'])
        self.btn((6, 151, 40, 16), 'PAUSE' if f['play'] else 'PLAY', lambda: f.update(play=not f['play']), col=ACC)
        self.btn((50, 151, 24, 16), '-1', lambda: f.update(t=clamp(f['t'] - 1, 0, TMAX), play=False))
        self.btn((78, 151, 24, 16), '+1', lambda: f.update(t=clamp(f['t'] + 1, 0, TMAX), play=False))
        self.btn((106, 151, 28, 16), '%dx' % f['speed'], lambda: f.update(speed=1 if f['speed'] > 1 else 4))
        self.btn((138, 151, 54, 16), 'RESTART', lambda: f.update(t=0.0, play=False))
        tl = pygame.Rect(8, 172, SW - 16, 12)
        pygame.draw.rect(S, (6, 10, 12), tl)
        for g in segs:
            x0 = tl.x + int(g['t0'] / TMAX * tl.w)
            x1 = tl.x + max(int(g['t1'] / TMAX * tl.w), x0 + 2)
            pygame.draw.rect(S, (60, 130, 120), (x0, tl.y + 2, x1 - x0, tl.h - 4))
        pygame.draw.rect(S, LINE, tl, 1)
        px = tl.x + int(t / TMAX * tl.w)
        pygame.draw.rect(S, WHITE, (px - 1, tl.y - 2, 3, tl.h + 4))
        if self.down and tl.inflate(0, 12).collidepoint(self.m) and self.now - self.trans > .2:
            f['t'] = clamp((self.m[0] - tl.x) / float(tl.w) * TMAX, 0, TMAX)
            f['play'] = False
        self.text('Drag to seek / green = motion', 8, 187, DIM)
        y = 199
        for g in segs:
            if g['t0'] <= t <= g['t1']:
                y = self.para('%s: %s' % (fmt(g['t0']), g['text']), 8, y, 182, AMB)
        if f['cam'] == 'Corridor':
            self.para('Doors: ' + '  '.join('%d %s' % (j + 1, r) for j, r in enumerate(c['rooms'][1:])), 8, 228, 182, DIM)

        def draw(y, w):
            y0 = y
            for g in segs:
                self.btn((4, y, w, 14), 'Jump to %s  motion clip' % fmt(g['t0']), lambda tt=g['t0']: f.update(t=float(tt), play=False), align='l')
                y += 16
            return y - y0
        self.scrollv((0, 250, SW, SH - 250), draw)

    # -- prints
    def d_print(self):
        c, S = self.case, self.S
        self.tile_back()
        i = self.sub.get('i')
        if i is None:
            self.header('FINGERPRINTS')
            lifted = [p for p in c['prints'] if p['lifted']]
            if not lifted:
                self.para('No prints yet. Open Inspect, find objects in the scene, and tap LIFT PRINT when you see one.', 6, 36, 186, DIM)
            y = 36
            for p in lifted:
                self.btn((6, y, SW - 12, 26), 'Print on %s%s' % (p['where'], '  [matched]' if p['done'] else ''), lambda pid=p['id']: self.go('print', i=pid), align='l')
                y += 30
            return
        p = c['prints'][i]
        self.header('MATCH THE PRINT')
        rnd = random.Random(i + c['T'])
        smudge = [(rnd.randint(-22, 14), rnd.randint(-22, 14), rnd.randint(6, 14), rnd.randint(5, 10)) for _ in range(5)]
        pygame.draw.rect(S, (8, 14, 14), (6, 33, 70, 70))
        pygame.draw.rect(S, LINE, (6, 33, 70, 70), 1)
        draw_print(S, 41, 68, c['sus'][p['target']]['pat'], 28, (140, 210, 190), smudge)
        self.text('SCENE PRINT', 41, 105, AMB, center=True)
        self.para('Partial and smudged. Compare ridge shape (circles, tall ovals, arcs, twin circles), spacing and scars. '
                  'Tap the file print that matches.', 82, 34, 112, DIM)
        res = self.sub.get('res')
        if res:
            self.para(res[0], 82, 82, 112, res[1])

        def draw(y, w):
            y0 = y
            for j, s in enumerate(c['sus']):
                x = 4 + (j % 2) * 88
                yy = y + (j // 2) * 76
                r = pygame.Rect(x, yy, 84, 72)
                self.btn(r, '', lambda jj=j: self.try_print(i, jj), bg=(14, 20, 26), en=not p['done'] and not self.sub.get('scan'))
                draw_print(self.S, r.centerx, r.y + 30, s['pat'], 24, ACC)
                self.text(fit(s['name'], F1, 80), r.centerx, r.y + 58, TXT, center=True)
                sc = self.sub.get('scan')
                if sc and sc[0] == j:
                    q = (self.now - sc[1]) / 1.2
                    pygame.draw.line(self.S, WHITE, (r.x + 2, r.y + int(60 * min(q, 1))), (r.right - 2, r.y + int(60 * min(q, 1))), 2)
            return ((len(c['sus']) + 1) // 2) * 76
        self.scrollv((0, 122, SW, SH - 122), draw)
        sc = self.sub.get('scan')
        if sc and self.now - sc[1] > 1.2:
            self.sub['scan'] = None
            ok = c['sus'][sc[0]]['pat'] == c['sus'][p['target']]['pat']
            p['tries'] += 1
            if ok:
                p['done'] = True
                self.find(p['ev'])
                self.sub['res'] = ('COMPATIBLE: %s' % c['sus'][sc[0]]['name'], ACC)
            else:
                self.sub['res'] = ('No match. The ridge pattern differs. Try another.', RED)
                self.snd('bad')
                self.glitch = .3

    def try_print(self, i, j):
        self.sub['scan'] = (j, self.now)
        self.sub['res'] = None

    # -- inspect
    def d_insp(self):
        c, S = self.case, self.S
        self.tile_back()
        rooms = c['rooms']
        room = self.sub['room']
        self.header('INSPECT')
        ri = rooms.index(room)
        self.btn((6, 32, 22, 16), '<', lambda: self.sub.update(room=rooms[(ri - 1) % 6], sel=None))
        self.btn((170, 32, 22, 16), '>', lambda: self.sub.update(room=rooms[(ri + 1) % 6], sel=None))
        self.text(room, 99, 35, TXT, center=True)
        pr = pygame.Rect(6, 52, 186, 112)
        draw_photo(S, pr, room, self.mn)
        old = S.get_clip()
        S.set_clip(old.clip(pr))
        off = (0, 0)
        for j, h in enumerate(c['insp'][room]):
            hr = pygame.Rect(h['rect']).move(pr.x + off[0], pr.y + off[1])
            seen = self.sub.get('seen', set())
            hov = hr.collidepoint(self.m)
            draw_obj(S, h['kind'], hr, hov)
            mk = (hr.right - 6, hr.y + 6)
            if (room, j) in seen:
                pygame.draw.circle(S, ACC, mk, 4, 1)
                pygame.draw.line(S, ACC, (mk[0] - 2, mk[1]), (mk[0], mk[1] + 2))
                pygame.draw.line(S, ACC, (mk[0], mk[1] + 2), (mk[0] + 3, mk[1] - 2))
            else:
                pygame.draw.circle(S, AMB, mk, 3 + int(math.sin(self.now * 5) + 1), 1)
            if hr.clip(pr).w > 4:
                self.btns.append((hr.clip(pr), lambda jj=j: self.pick_spot(room, jj)))
        S.set_clip(old)
        pygame.draw.rect(S, LINE, pr, 1)
        sel = self.sub.get('sel')
        spots = c['insp'][room]
        if sel is not None and sel < len(spots):
            h = spots[sel]
            self.text(h['name'], 6, 168, ACC, F2)
            S.set_clip(pygame.Rect(6,182,186,77))
            y, _ = self.para_typed(h['text'], 6, 182, 186, self.sub.get('st', self.now), TXT)
            S.set_clip(None)
            y = min(y, 259)
            if h['prn'] is not None:
                p = c['prints'][h['prn']]
                if p['lifted']:
                    self.text('Print lifted. Open the Prints app.', 6, y + 2, ACC)
                else:
                    self.btn((6, y + 2, 100, 18), 'LIFT PRINT', lambda pp=p: self.lift(pp))
            if h['ev'] is not None:
                self.find(h['ev'])
                self.btn((6,264,186,20),'READ FULL EXHIBIT',lambda eid=h['ev']:self.go('evid',detail=eid))
        else:
            self.para('Tap the glowing objects in the photo (or move the mouse to shift the view).', 6, 170, 186, DIM)
        if sel is None:
            self.text('Select an object to inspect it.',6,270,DIM)

    def pick_spot(self, room, j):
        self.sub.setdefault('seen', set()).add((room, j))
        self.sub['sel'] = j
        self.sub['st'] = self.now
        if self.case['insp'][room][j]['kind'] == 'window':
            self.glitch = .5
            self.snd('glitch')

    def lift(self, p):
        p['lifted'] = True
        self.snd('good')
        self.toast('Print lifted from %s' % p['where'])

    # -- interview
    def d_intr(self):
        c, S = self.case, self.S
        self.tile_back()
        i = self.sub.get('i')
        if i is None:
            self.header('INTERVIEW')

            def draw(y, w):
                y0 = y
                for j, s in enumerate(c['sus']):
                    self.btn((4, y, w, 34), '', lambda jj=j: self.go('intr', i=jj), bg=(14, 20, 26))
                    draw_portrait(self.S, pygame.Rect(8, y + 3, 28, 28), s)
                    self.text(s['name'], 42, y + 6, TXT)
                    self.text(s['role'], 42, y + 18, DIM)
                    y += 37
                return y - y0
            self.scrollv((0, 32, SW, SH - 32), draw)
            return
        s = c['sus'][i]
        self.header('INTERVIEW')
        draw_portrait(S, pygame.Rect(6, 33, 52, 52), s)
        self.text(s['name'], 64, 36, TXT, F2)
        self.text(s['role'], 64, 52, DIM)
        self.text('Phone: ' + ('555-%04d' % (1000 + i * 137)), 64, 64, DIM)
        if self.sub.get('pick'):
            self.text('Choose a clue to show them:', 6, 90, AMB)
            found = [e for e in c['ev'] if e['found']]

            def draw(y, w):
                y0 = y
                for e in found:
                    self.btn((4, y, w, 22), '[%s] %s' % (e['src'], e['title']), lambda ee=e: self.present(i, ee['id']), align='l')
                    y += 25
                return y - y0
            self.scrollv((0, 102, SW, SH - 102), draw)
            return
        for j, qd in enumerate(c['intr'][i]):
            if j == 3:
                self.btn((6, 90 + j * 22, SW - 12, 20), 'Present evidence...', lambda: self.sub.update(pick=True), col=AMB)
            else:
                self.btn((6, 90 + j * 22, SW - 12, 20), qd['q'], lambda jj=j: self.ask(i, jj), align='l')
        ans = self.sub.get('ans')
        if ans:
            pygame.draw.rect(S, PANEL, (6, 182, SW - 12, 100), border_radius=3)
            self.para_typed(ans[0], 10, 186, 178, ans[1], TXT)

    def ask(self, i, j):
        q = self.case['intr'][i][j]
        self.sub['ans'] = (q['a'], self.now)
        if q['ev'] is not None:
            self.find(q['ev'])

    def present(self, i, eid):
        c = self.case
        e = c['ev'][eid]
        s = c['sus'][i]
        self.sub['pick'] = False
        if e['subj'] == i and e['kind'] == 'inc':
            if i == c['killer']:
                q = c['intr'][i][3]
                a = q['a']
                if q['ev'] is not None:
                    self.find(q['ev'])
                self.glitch = .6
                self.snd('glitch')
            else:
                a = 'That is not true.'
        elif e['subj'] == i and e['kind'] == 'sus':
            a = c['explain'].get(i, 'So I had a motive. So does everyone here. It proves nothing.')
        elif e['subj'] == i and e['kind'] == 'clr':
            a = 'Exactly. That proves I could not have done it.'
        elif e['subj'] == i:
            a = 'Yes, that is me. So what?'
        else:
            a = 'I do not see what that has to do with me.'
        self.sub['ans'] = (a, self.now)

    # -- notes
    def d_notes(self):
        c = self.case
        self.tile_back()
        self.header('NOTES')

        def draw(y, w):
            y0 = y
            self.text('CASE FACTS', 4, y, AMB)
            y += 12
            for ln in ['Victim: %s' % c['victim'], 'Place: %s, %s' % (c['venue'], c['R']), 'Method: examine the scene log',
                       'Time: verify the logger clock', 'Cams: Corridor and %s' % c['lobby']]:
                self.text(fit(ln, F1, w), 4, y, TXT)
                y += 11
            y += 5
            self.text('SUSPECTS  (tap to mark)', 4, y, AMB)
            y += 12
            for j, s in enumerate(c['sus']):
                lab, col = (('?', DIM), ('CLEARED', ACC), ('SUSPECT', RED))[self.marks[j]]
                known = c['ev'][j]['found']
                self.btn((4, y, w, 24), '', lambda jj=j: self.mark(jj), bg=(14, 20, 26))
                self.text(fit(s['name'], F1, w - 64), 8, y + 2, TXT)
                self.text(fit(s['role'] + (', %s coat' % s['coat'] if known else ', coat unknown'), F1, w - 64), 8, y + 13, DIM)
                self.text(lab, 4 + w - 6, y + 8, col, right=True)
                y += 27
            y += 4
            self.text('CLUE LOG', 4, y, AMB)
            y += 12
            for e in c['ev']:
                if e['found'] and e['src'] != 'LINK':
                    self.text('- ' + fit(e['title'], F1, w - 10), 4, y, SRC_COL.get(e['src'],DIM))
                    y += 11
            return y - y0
        self.scrollv((0, 32, SW, SH - 32), draw)

    def mark(self, j):
        self.marks[j] = (self.marks[j] + 1) % 3

    # -- evidence board
    def d_evid(self):
        self.tile_back();self.header('EVIDENCE / EXHIBITS')
        if self.investigation_detail():return
        if self.sub.get('folder'):
            self.draw_accusation_folder();return
        self.btn((6,32,186,24),'ACCUSATION FOLDERS',lambda:(self.sub.update(folder=True),setattr(self,'scroll',0)))
        def draw(y,w):
            top=y
            for e in self.case['ev']:
                if e['found']:
                    self.btn((4,y,w,25),'[%s] %s' % (e['src'],e['title']),lambda eid=e['id']:self.show_finding(eid),align='l')
                    y+=29
            return y-top
        self.scrollv((0,62,SW,SH-62),draw)

    def toggle_ev(self, eid):
        self.emsg = ''
        if eid in self.esel:
            self.esel.remove(eid)
        else:
            if len(self.esel) == 2:
                self.esel.pop(0)
            self.esel.append(eid)

    # -- accuse
    def d_accuse(self):
        c, a, S = self.case, self.acc, self.S
        self.tile_back()
        self.header('ACCUSATION')
        if a['stage'] == 0:
            self.para('Who is responsible? Chances left: %d' % self.chances, 6, 33, 186, AMB)
            if a['msg']:
                self.para(a['msg'], 6, 45, 186, RED)

            def draw(y, w):
                y0 = y
                for j, s in enumerate(c['sus']):
                    self.btn((4, y, w, 34), '', lambda jj=j: a.update(s=jj), bg=(14, 20, 26), sel=(a['s'] == j))
                    draw_portrait(self.S, pygame.Rect(8, y + 3, 28, 28), s)
                    self.text(s['name'], 42, y + 6, TXT)
                    self.text(s['role'], 42, y + 18, DIM)
                    y += 37
                return y - y0
            self.scrollv((0, 74, SW, SH - 74 - 26), draw)
            self.btn((20, SH - 22, 158, 18), 'NEXT: LOAD EXHIBITS', lambda:self.prepare_accusation(a['s']), en=a['s'] is not None, col=AMB)
            return
        if a['stage'] == 2:
            self.draw_reconstruction()
            return
        person=a['s']
        a['ev']=[eid for key,label,eid in self.accusation_items(person) if c['ev'][eid]['found']]
        self.text(fit(c['sus'][person]['name'],F2,186),6,34,AMB,F2)
        self.para('Collected exhibits loaded: %d/3. Read them below. Complete means collected, not proven guilty.' % len(a['ev']),6,54,186,DIM)
        y=99
        for key,label,eid in self.accusation_items(person):
            found=c['ev'][eid]['found']
            self.btn((6,y,186,27),('SAVED: ' if found else 'MISSING: ')+label,
                     lambda eid=eid,key=key:self.go('evid',detail=eid) if c['ev'][eid]['found'] else self.locate_accusation_item(person,key),col=ACC if found else AMB)
            y+=32
        prerequisites=all(c['ev'][eid]['found'] for eid in (c['incident_ev'],c['clock_ev']))
        for j,(eid,label,fn) in enumerate([(c['incident_ev'],'SCENE LOG',lambda:self.go('insp',room=c['R'],sel=None)),(c['clock_ev'],'CLOCK MESSAGE',lambda:self.open_thread(c['wit']))]):
            found_log=c['ev'][eid]['found']
            self.btn((6,201+j*24,186,21),('READ: ' if found_log else 'FIND: ')+label,lambda eid=eid,fn=fn:self.go('evid',detail=eid) if c['ev'][eid]['found'] else fn(),col=ACC if found_log else AMB)
        self.btn((4,SH-24,60,22),'BACK',lambda:a.update(stage=0))
        self.btn((68,SH-24,126,22),'EXPLAIN',lambda:(a.update(stage=2),setattr(self,'scroll',0)),en=len(a['ev'])==3 and prerequisites,col=ACC)

    def accusation_items(self,person):
        return [(key,label,self.case['artifacts'][key][person]) for key,label in
                [('photo','Portrait'),('device','Handset archive'),('web','Public entry')]]

    def prepare_accusation(self,person):
        self.acc=dict(s=person,ev=[eid for key,label,eid in self.accusation_items(person) if self.case['ev'][eid]['found']],stage=1,msg='')
        self.go('accuse',push=self.scr!='accuse')

    def locate_accusation_item(self,person,key):
        if key=='photo':self.go('photos',person=person,zoom=1)
        elif key=='device':self.open_device(person)
        else:
            self.enter_desk('laptop');self.laptop_browser=True
            self.search_text=self.case['sus'][person]['name'];self.sync_keyboard()

    def draw_accusation_folder(self):
        c=self.case;person=self.sub.get('person')
        if person is None:
            self.para('Each person has a folder. Saved clues appear automatically. 3/3 means collected, not guilty.',6,33,186,DIM)
            def draw(y,w):
                top=y
                for i,p in enumerate(c['sus']):
                    count=sum(c['ev'][eid]['found'] for key,label,eid in self.accusation_items(i))
                    self.btn((5,y,w-10,32),p['name']+'  '+str(count)+'/3',lambda i=i:(self.sub.update(person=i),setattr(self,'scroll',0)),align='l');y+=37
                return y-top
            self.scrollv((0,83,SW,166),draw)
            self.btn((6,257,186,23),'ALL EVIDENCE',lambda:(self.sub.clear(),setattr(self,'scroll',0)))
            return
        self.text(fit(c['sus'][person]['name'],F2,186),6,34,AMB,F2)
        y=60
        for key,label,eid in self.accusation_items(person):
            found=c['ev'][eid]['found']
            self.btn((6,y,186,30),('SAVED: ' if found else 'FIND: ')+label,
                     lambda eid=eid,key=key:self.show_finding(eid) if c['ev'][eid]['found'] else self.locate_accusation_item(person,key),col=ACC if found else AMB)
            y+=35
        self.para('Saved: tap to read. Missing: tap to go find it. Compare these clues before choosing this person.',6,172,186,DIM)
        self.btn((6,226,186,24),"USE THIS PERSON'S EXHIBITS",lambda:self.prepare_accusation(person))
        self.btn((6,257,186,23),'BACK TO FOLDERS',lambda:(self.sub.pop('person',None),setattr(self,'scroll',0)))

    def draw_reconstruction(self):
        c,a=self.case,self.acc
        def draw(y,w):
            top=y
            y=self.para('When did it happen in station time? Correct the clock from the messages.',6,y,w-8,AMB)+8
            for t in c['time_choices']:
                self.btn((4,y,w,22),fmt(t-2)+' - '+fmt(t+2),lambda t=t:a.update(when=t),sel=a.get('when')==t);y+=26
            y=self.para('How was it done? Use the physical scene evidence.',6,y,w-8,AMB)+8
            for method in c['method_choices']:
                height=max(32,len(wrap(method,F1,w-18))*12+8)
                self.btn((4,y,w,height),'',lambda method=method:a.update(method=method),sel=a.get('method')==method)
                self.para(method,9,y+4,w-18,TXT);y+=height+4
            return y-top
        self.scrollv((0,34,SW,218),draw)
        self.btn((4,262,58,20),'BACK',lambda:(a.update(stage=1),setattr(self,'scroll',0)))
        self.btn((68,262,126,20),'SUBMIT CASE',self.submit_accuse,en=a.get('when') is not None and a.get('method') is not None,col=RED)

    def pick_proof(self, eid):
        a = self.acc
        if eid in a['ev']:
            a['ev'].remove(eid)
        elif len(a['ev']) < 3:
            a['ev'].append(eid)

    def show_finding(self, eid):
        self.find(eid)
        self.sub['detail'] = eid
        self.scroll = 0

    def investigation_detail(self):
        eid = self.sub.get('detail')
        if eid is None:
            return False
        e = self.case['ev'][eid]
        def draw(y, w):
            return self.para(e['title']+'\n\n'+e['text'], 6, y, w-8, TXT)-y
        self.scrollv((0, 36, SW, 214), draw)
        self.btn((8, 256, 182, 22), 'BACK TO APP', lambda: (self.sub.pop('detail', None), setattr(self, 'scroll', 0)))
        return True

    def mark_comparison(self, source, i):
        c=self.case
        c[source+'_seen'].add(i)
        if source=='message':
            if i in c['device_seen']: self.find(c['artifacts']['device'][i])
        elif source=='device':
            if i in c['message_seen']: self.find(c['artifacts']['device'][i])
        else:self.find(c['artifacts'][source][i])

    def d_photos(self):
        self.tile_back(); self.header('SUSPECT PHOTOS')
        if self.investigation_detail(): return
        c = self.case; i = self.sub.get('person')
        if i is None:
            self.text('Open portrait / zoom badge / compare', 6, 34, DIM)
            def draw(y,w):
                top=y
                for j,p in enumerate(c['sus']):
                    self.btn((4,y,w,38),'',lambda j=j:self.go('photos',person=j,zoom=1))
                    draw_portrait(self.S,pygame.Rect(8,y+3,30,30),p)
                    self.text(fit(p['name'],F1,130),44,y+5,TXT)
                    self.text('Badge inspected' if j in c['photo_seen'] else 'Badge unread',44,y+20,ACC if j in c['photo_seen'] else DIM)
                    y+=42
                return y-top
            self.scrollv((0,52,SW,195),draw)
            self.text('%d portrait exhibits saved' % len(c['photo_seen']),6,260,AMB)
            return
        if self.difficulty=='Experienced':self.btn((11,264,176,18),'BACKGROUND / HIDDEN DETAILS',lambda:self.go('secrets',person=i,focus=0,zoom=1))
        p=c['sus'][i]; z=self.sub.get('zoom',1)
        self.text(p['name'],6,34,TXT)
        photo=pygame.Surface((176,150));photo.fill((24,31,34))
        draw_portrait(photo,pygame.Rect(30,7,116,140),p)
        badge=pygame.Rect(103,111,29,18)
        pygame.draw.rect(photo,(210,205,172),badge)
        code=c['badges'][i]
        photo.blit(F1.render(code,True,(20,29,31)),(104,115))
        viewport=pygame.Rect(11,53,176,150)
        if z==1:
            self.S.blit(photo,viewport)
            target=badge.move(viewport.x,viewport.y)
        else:
            # Crop around the actual badge pixels; magnification reveals the original photo.
            cw,ch=176//z,150//z
            crop=pygame.Rect(0,0,cw,ch);crop.center=badge.center;crop.clamp_ip(photo.get_rect())
            self.S.blit(pygame.transform.scale(photo.subsurface(crop),(176,150)),viewport)
            target=pygame.Rect(viewport.x+(badge.x-crop.x)*z,viewport.y+(badge.y-crop.y)*z,badge.w*z,badge.h*z)
        self.photo_target = target.clip(viewport)
        pygame.draw.rect(self.S,AMB,target,1)
        self.btns.append((target.clip(viewport),lambda:self.mark_comparison('photo',i) if z>=2 else self.sub.update(zoom=2)))
        self.text('ARCHIVE '+fmt(c['T']-40)+' / '+str(z)+'x',14,55,DIM)
        self.btn((11,209,45,22),'-',lambda:self.sub.update(zoom=max(1,z//2)))
        self.btn((61,209,45,22),'+',lambda:self.sub.update(zoom=min(4,z*2)))
        self.btn((112,209,75,22),'ALL PHOTOS',lambda:self.go('photos',push=False))
        self.para('Badge '+code+' recorded.' if i in c['photo_seen'] else 'Zoom to 2x or 4x, then click the outlined badge to record the clue.',11,240,176,ACC if i in c['photo_seen'] else DIM)

    def enter_desk(self, screen):
        if screen == 'laptop': self.laptop_browser = False
        if screen=='drawer' and self.difficulty=='Experienced':self.case['expert']['drawer_open']=False
        self.desktop=screen;self.desk_scroll=0;self.profile=None
        self.desk_buttons=[];self.down=False
        self.sync_keyboard()

    def save_notebook(self):
        try:
            tmp=self.note_path.with_suffix('.tmp')
            tmp.write_text(json.dumps(self.notebooks,ensure_ascii=False,indent=2))
            tmp.replace(self.note_path)
            self.note_status='Saved locally'
        except OSError:
            self.note_status='Cannot save here; notes kept in memory'

    def notebook_page(self, step):
        keys=list(self.notebooks);j=keys.index(self.note_key)
        self.note_key=keys[clamp(j+step,0,len(keys)-1)];self.desk_scroll=0

    def handle_desk(self,e):
        if e.type==pygame.QUIT:self.running=False
        elif e.type==pygame.MOUSEBUTTONDOWN and e.button==1:
            point=((e.pos[0]-self.desk_x)/self.desk_scale,(e.pos[1]-self.desk_y)/self.desk_scale)
            self.board_pointer=point
            for r,fn in reversed(self.desk_buttons):
                if r.collidepoint(point):fn();break
            if self.desktop=='board':
                ex=self.case['expert'];j=ex['selected']
                self.board_drag=j if not ex['picker'] and ex['mode']=='move' and j is not None and pygame.Rect(ex['board'][j]['x'],ex['board'][j]['y'],106,44).collidepoint(point) else None
        elif e.type==pygame.MOUSEBUTTONUP:
            self.board_drag=None
        elif e.type==pygame.MOUSEMOTION and self.desktop=='board' and getattr(self,'board_drag',None) is not None and getattr(e,'buttons',(0,))[0]:
            self.board_place(((e.pos[0]-self.desk_x)/self.desk_scale,(e.pos[1]-self.desk_y)/self.desk_scale))
        elif e.type==pygame.MOUSEWHEEL:
            self.desk_scroll=clamp(self.desk_scroll-e.y*24,0,getattr(self,'desk_max',0))
        elif e.type==pygame.KEYDOWN:
            if e.key==pygame.K_ESCAPE:
                if self.desktop=='desk':self.desktop=None
                else:self.enter_desk('desk')
            elif self.desktop=='notebook':
                text=self.notebooks[self.note_key]
                if e.key==pygame.K_BACKSPACE:text=text[:-1]
                elif e.key==pygame.K_RETURN:text+='\n'
                elif not self.mobile and e.unicode and e.unicode.isprintable():text+=e.unicode
                self.notebooks[self.note_key]=text
                self.save_notebook();self.desk_scroll=10**8
            elif self.desktop=='laptop' and self.laptop_browser and self.profile is None:
                if e.key==pygame.K_BACKSPACE:self.search_text=self.search_text[:-1]
                elif not self.mobile and e.unicode and e.unicode.isprintable():self.search_text=(self.search_text+e.unicode)[:60]
                self.desk_scroll=0

    def render_desk(self):
        self.win=pygame.display.get_surface();W,H=self.win.get_size()
        surface=pygame.Surface((400,420));surface.fill((13,18,21))
        self.desk_scale=min(W/400,H/420);self.desk_x=(W-400*self.desk_scale)/2;self.desk_y=(H-420*self.desk_scale)/2
        mx,my=self.touch_pos if self.mobile else pygame.mouse.get_pos();mouse=((mx-self.desk_x)/self.desk_scale,(my-self.desk_y)/self.desk_scale)
        self.desk_buttons=[];self.desk_max=0
        def text(t,x,y,col=TXT,font=None):surface.blit((font or F2).render(t,True,col),(x,y))
        def button(rect,label,fn,tip=''):
            r=pygame.Rect(rect);hover=r.collidepoint(mouse)
            pygame.draw.rect(surface,(48,67,64) if hover else PANEL2,r,border_radius=3)
            pygame.draw.rect(surface,ACC if hover else LINE,r,1,border_radius=3)
            text(label,r.x+7,r.y+7)
            self.desk_buttons.append((r,fn))
            if hover and tip:text(tip,12,390,AMB,F1)
        def body(content,top=100,bottom=345):
            lines=wrap(content,F2,364);step=18
            self.desk_max=max(0,len(lines)*step-(bottom-top))
            self.desk_scroll=clamp(self.desk_scroll,0,self.desk_max)
            surface.set_clip((12,top,376,bottom-top))
            for j,line in enumerate(lines):text(line,18,top+j*step-self.desk_scroll)
            surface.set_clip(None)
            if self.desk_max:text('Mouse wheel to scroll',18,bottom+2,DIM,F1)
        c=self.case
        if self.desktop=='board':
            self.draw_board(surface,mouse)
        elif self.desktop=='interrogation':
            self.draw_interrogation(surface,mouse)
        elif self.desktop=='desk':
            surface.fill((24,29,32))
            # Wall, pool of lamplight, beveled wooden desktop and drawer fascia.
            for x in range(0,400,25):pygame.draw.line(surface,(29,35,37),(x,0),(x,72))
            pygame.draw.polygon(surface,(97,70,45),[(16,71),(383,71),(400,315),(0,315)])
            rng=random.Random(32)
            for y in range(76,313,5):
                pygame.draw.lines(surface,(110+rng.randrange(10),79,49),False,[(0,y),(100,y+rng.randrange(-2,3)),(270,y-1),(400,y+2)])
            pygame.draw.rect(surface,(53,36,27),(0,315,400,72))
            pygame.draw.line(surface,(154,111,64),(0,315),(400,315),3)
            pygame.draw.rect(surface,(85,59,39),(22,328,338,44),border_radius=3)
            pygame.draw.rect(surface,(32,25,22),(22,328,338,44),2,border_radius=3)
            pygame.draw.rect(surface,(161,140,95),(155,340,72,11),border_radius=4)
            pygame.draw.rect(surface,(35,27,23),(164,343,54,4),border_radius=2)
            # Laptop hinge, tilted display, keyboard deck, keys and trackpad.
            pygame.draw.ellipse(surface,(47,35,28),(137,182,244,39))
            pygame.draw.polygon(surface,(15,20,25),[(156,82),(359,82),(365,175),(148,175)])
            pygame.draw.polygon(surface,(77,88,94),[(156,82),(359,82),(365,175),(148,175)],2)
            pygame.draw.polygon(surface,(23,42,52),[(164,91),(350,91),(355,164),(158,164)])
            pygame.draw.circle(surface,(145,177,174),(213,120),19)
            pygame.draw.circle(surface,(23,42,52),(221,114),18)
            text('NIGHT OS',275,141,DIM,F1)
            pygame.draw.circle(surface,(130,144,146),(257,86),1)
            pygame.draw.polygon(surface,(100,109,112),[(148,175),(365,175),(383,209),(130,209)])
            pygame.draw.line(surface,(154,158,153),(132,210),(382,210),2)
            for row in range(3):
                for col in range(14):pygame.draw.rect(surface,(37,45,50),(151+col*15-row*3,179+row*7,12,5),border_radius=1)
            pygame.draw.rect(surface,(65,77,83),(227,200,55,7),1,border_radius=2)
            # Pocket phone, earpiece, glass, app icons and home ring.
            pygame.draw.rect(surface,(43,32,28),(30,154,71,123),border_radius=12)
            pygame.draw.rect(surface,(12,16,22),(24,148,71,123),border_radius=12)
            pygame.draw.rect(surface,(122,128,126),(24,148,71,123),1,border_radius=12)
            pygame.draw.rect(surface,(22,43,46),(30,161,59,89),border_radius=3)
            pygame.draw.line(surface,(106,114,115),(49,154),(69,154),2)
            pygame.draw.circle(surface,(127,151,148),(59,260),5,1)
            text('03:33',39,174,ACC,F1)
            for j in range(6):pygame.draw.rect(surface,[BLUE,ACC,AMB][j%3],(37+(j%3)*16,199+(j//3)*19,11,12),border_radius=2)
            # Open notebook with curved covers, paper leaves, binding and ink.
            pygame.draw.polygon(surface,(36,44,40),[(143,224),(241,219),(353,227),(358,303),(245,309),(137,300)])
            pygame.draw.polygon(surface,(222,209,170),[(148,227),(241,224),(242,302),(143,296)])
            pygame.draw.polygon(surface,(237,224,187),[(245,224),(348,231),(352,299),(246,303)])
            pygame.draw.line(surface,(109,89,65),(243,225),(244,302),2)
            for y in range(240,292,9):
                pygame.draw.line(surface,(150,170,160),(155,y),(232,y-2))
                pygame.draw.line(surface,(150,170,160),(254,y-1),(341,y+3))
            for y in range(235,299,13):pygame.draw.arc(surface,(79,85,75),(237,y,13,7),0,math.pi,2)
            pygame.draw.line(surface,(29,56,67),(364,234),(374,293),4)
            pygame.draw.polygon(surface,(194,174,125),[(372,293),(376,293),(376,300)])
            # Desk lamp and mug are decorative objects with recognizable silhouettes.
            pygame.draw.ellipse(surface,(16,22,23),(19,115,77,17))
            pygame.draw.line(surface,(72,87,81),(57,119),(40,73),6)
            pygame.draw.line(surface,(72,87,81),(40,73),(80,43),5)
            pygame.draw.polygon(surface,(75,111,95),[(69,38),(87,38),(105,65),(54,65)])
            pygame.draw.ellipse(surface,(231,206,133),(54,59,51,10))
            pygame.draw.ellipse(surface,(46,33,27),(104,266,29,12))
            pygame.draw.ellipse(surface,(166,158,134),(107,240,24,31))
            pygame.draw.ellipse(surface,(57,38,27),(109,241,20,8))
            pygame.draw.arc(surface,(166,158,134),(124,245,16,17),-1.6,1.6,3)
            regions=[((130,80,253,134),'Laptop - open workstation',lambda:self.enter_desk('laptop')),
                     ((24,148,71,123),'Investigation phone - pick up',lambda:setattr(self,'desktop',None)),
                     ((137,219,220,89),'Notebook - write case notes',lambda:self.enter_desk('notebook')),
                     ((22,328,338,44),'Drawer - secured suspect phones',lambda:self.enter_desk('drawer'))]
            text('Move over an object to inspect it',16,392,DIM,F1)
            for rect,label,fn in regions:
                r=pygame.Rect(rect);self.desk_buttons.append((r,fn))
                if r.collidepoint(mouse):
                    pygame.draw.rect(surface,AMB,r.inflate(4,4),1,border_radius=5)
                    pygame.draw.rect(surface,(13,23,24),(0,385,400,35))
                    text(label,16,393,ACC,F1)
            button((10,26,178,28),'INTERROGATION ROOM',self.open_interrogation,'Choose a suspect and question their account')
            if self.difficulty=='Experienced':
                button((207,26,183,28),'EVIDENCE BOARD',lambda:self.enter_desk('board'))
                ex=c['expert']
                if ex['drawer_open']:
                    pygame.draw.rect(surface,(13,10,9),(24,329,334,8))
                    text('The drawer is slightly open.',28,375,AMB,F1)
                if ex['wake_until']>self.now:
                    pygame.draw.polygon(surface,(107,148,139),[(164,91),(350,91),(355,164),(158,164)])
                    text('NO INPUT DETECTED',179,124,(16,35,34),F1)
        elif self.desktop=='notebook':
            surface.fill((70,49,34))
            pygame.draw.rect(surface,(28,49,44),(13,32,374,331),border_radius=10)
            pygame.draw.rect(surface,(174,156,115),(23,40,358,313),border_radius=5)
            pygame.draw.rect(surface,(238,227,194),(25,38,350,310),border_radius=3)
            pygame.draw.rect(surface,(213,198,160),(25,38,20,310))
            for y in range(62,336,24):
                pygame.draw.circle(surface,(57,56,45),(37,y),3)
                pygame.draw.arc(surface,(157,166,158),(17,y-5,24,10),0,math.pi*1.8,2)
            pygame.draw.line(surface,(188,102,93),(67,92),(67,343),1)
            for y in range(112,345,18):pygame.draw.line(surface,(169,188,178),(47,y),(370,y),1)
            text('FIELD NOTES',73,51,(49,66,61))
            text(fit(self.note_key,F1,290),73,76,(105,102,81),F1)
            content=self.notebooks[self.note_key]+('|' if int(self.now*2)%2==0 else '')
            lines=wrap(content,F2,292);self.desk_max=max(0,len(lines)*18-234)
            self.desk_scroll=clamp(self.desk_scroll,0,self.desk_max)
            surface.set_clip((70,96,298,240))
            for j,line in enumerate(lines):text(line,74,98+j*18-self.desk_scroll,(40,62,70))
            surface.set_clip(None)
            text('Type on the page / '+self.note_status,20,13,TXT,F1)
            button((15,358,112,28),'PREVIOUS',lambda:self.notebook_page(-1))
            button((137,358,80,28),'NEXT',lambda:self.notebook_page(1))
            button((227,358,158,28),'BACK TO DESK',lambda:self.enter_desk('desk'))
            text('Mouse wheel scrolls the page',20,399,DIM,F1)
        elif self.desktop=='laptop':
            if not self.laptop_browser:
                surface.fill((20,31,47))
                for y in range(60,365):
                    pygame.draw.line(surface,(20+y//24,31+y//25,47+y//18),(0,y),(400,y))
                pygame.draw.circle(surface,(165,189,178),(95,112),35)
                pygame.draw.circle(surface,(28,40,56),(108,102),33)
                pygame.draw.polygon(surface,(13,26,33),[(0,350),(0,270),(85,205),(155,293),(235,183),(400,315),(400,350)])
                text('NIGHT OS',15,18,TXT)
                text('Investigation workstation',15,40,DIM,F1)
                button((298,22,87,68),'',self.open_browser,'Google: open fictional suspect search')
                colors=[BLUE,RED,AMB,BLUE,ACC,RED]
                x=306
                for ch,col in zip('Google',colors):
                    text(ch,x,35,col);x+=11
                text('Search',319,65,TXT,F1)
                pygame.draw.rect(surface,(12,20,28),(0,349,400,71))
                text('03:33  /  Archive connection ready',14,356,DIM,F1)
                button((12,378,376,30),'BACK TO DESK',lambda:self.enter_desk('desk'))
            else:
                text('Google / case web',12,15,ACC)
                text('Offline archive - fictional people only',12,39,DIM,F1)
                if self.profile is None:
                    button((12,58,328,32),self.search_text or 'Type a suspect name or occupation...',lambda:None)
                    button((346,58,42,32),'X',lambda:setattr(self,'search_text',''))
                    matches=[(i,p) for i,p in enumerate(c['sus']) if self.search_text.casefold() in (p['name']+' '+p['role']).casefold()]
                    if not matches:text('No matching profiles.',16,112,DIM)
                    for row,(i,p) in enumerate(matches):
                        button((12,104+row*37,376,32),p['name']+' / '+p['role'],lambda i=i:self.open_profile(i))
                    text('Profiles read: %d/%d' % (len(c['web_seen']),len(c['sus'])),12,339,AMB,F1)
                else:
                    p=c['sus'][self.profile]
                    text(p['name'],12,65,AMB)
                    body('Biography: '+p['name']+' works as '+p['role']+' at '+c['venue']+'.\n\nBackground: a reported dispute concerns '+p['motive']+'. This is context, not proof.\n\nArchived event page:\n'+c['routes'][self.profile]+'\n\nDates were verified against venue records. Compare the timestamp and journey duration with the corrected incident window.',100,320)
                    button((12,339,376,30),'BACK TO SEARCH',lambda:setattr(self,'profile',None))
                button((12,378,376,30),'BACK TO DESK',lambda:self.enter_desk('desk'))
        elif self.desktop=='drawer':
            text('SECURED PHONES / CASE EXHIBITS',12,18,AMB)
            text('Click a phone to inspect its archive',12,44,DIM,F1)
            pygame.draw.rect(surface,(75,53,36),(8,65,384,298),border_radius=5)
            pygame.draw.rect(surface,(36,26,23),(18,73,364,280),4)
            for i,p in enumerate(c['sus']):
                x=36+(i%3)*123;y=85+(i//3)*135
                r=pygame.Rect(x,y,77,105)
                pygame.draw.rect(surface,(11,14,19),r,border_radius=10)
                pygame.draw.rect(surface,(105,112,114),r,1,border_radius=10)
                pygame.draw.rect(surface,(29,48,52),(x+7,y+12,63,73),border_radius=3)
                pygame.draw.rect(surface,(88,96,97),(x+28,y+5,21,2))
                pygame.draw.circle(surface,DIM,(x+38,y+95),5,1)
                draw_portrait(surface,pygame.Rect(x+21,y+24,35,40),p)
                text('READ' if i in c['device_seen'] else 'SEALED',x+20,y+70,ACC,F1)
                self.desk_buttons.append((r,lambda i=i:self.open_device(i)))
                text(p['first'],x+3,y+109,TXT,F1)
                if r.collidepoint(mouse):pygame.draw.rect(surface,ACC,r.inflate(4,4),1,border_radius=11)
            button((12,378,376,30),'BACK TO DESK',lambda:self.enter_desk('desk'))
        if self.difficulty=='Experienced' and self.case['expert'].get('notice_until',0)>self.now:
            pygame.draw.rect(surface,(10,18,20),(5,404,390,16))
            text(self.case['expert']['notice'],10,406,AMB,F1)
        if self.guide and self.difficulty!='Experienced': self.draw_desk_guide(surface)
        self.win.fill((5,7,9))
        scaled=pygame.transform.smoothscale(pygame.transform.scale(surface,(800,840)),(int(400*self.desk_scale),int(420*self.desk_scale)))
        self.win.blit(scaled,(self.desk_x,self.desk_y));self.draw_corner_pip();pygame.display.flip()

    def open_interrogation(self):
        self.enter_desk('interrogation')
        self.room_person=None
        self.room_view='choose'
        self.room_answer=''
        self.case.setdefault('room_history',{})

    def seat_suspect(self,i):
        self.room_person=i;self.room_view='questions';self.desk_scroll=0
        self.snd('click')

    def room_questions(self):
        c=self.case;i=self.room_person;p=c['sus'][i]
        questions = [
            ('Where were you that evening?',
             'I was in '+c['claim'][i]+'. I remember checking in, but I did not watch the clock the whole time. The public attendance entry should give the exact check-in time.',None),
            ('What was your connection to the case?',
             'I work as '+p['role']+'. There was a dispute about '+p['motive']+'. You should check what actually happened, not just who had an argument.',None),
            ('Explain the badge in your portrait.',
             'That is access badge '+c['badges'][i]+'. More than one person belongs to that access group. The portrait shows what I wore earlier; it does not show every room I visited.',c['artifacts']['photo'][i]),
            ('Which device label were you using?',
             'The archive keeps both labels, even after replacement. The service desk sent the changeover time in a message. Before that minute the previous group applies; from that minute the replacement applies. Compare it to the incident in station time.',c['artifacts']['device'][i]),
            ('Your public record: explain the timing.',
             'That entry is a face-to-face check-in, not a record of my entire evening. The route duration is a minimum. Add it to the check-in time before comparing it with the scene. I stand by my account.',c['artifacts']['web'][i])]
        if self.difficulty=='Experienced':
            ex=c['expert']; detail=ex['details'][i][i%5]
            questions += [('Anything unusual before the portrait?',ex['claims'][i],None),('CHALLENGE: show '+detail['label'],ex['replies'][i],detail['eid'])]
        return questions

    def ask_in_room(self,j):
        question,answer,required=self.room_questions()[j]
        if required is not None and not self.case['ev'][required]['found']:return
        if j==6 and self.difficulty=='Experienced' and 5 not in self.case['room_history'].get(self.room_person,{}):
            self.room_answer='Ask about anything unusual before the portrait first, then present the conflicting detail.';self.room_view='answer';return
        i=self.room_person
        history=self.case['room_history'].setdefault(i,{})
        if j not in history:
            eid=len(self.case['ev'])
            self.case['ev'].append(dict(id=eid,title='Interview / '+self.case['sus'][i]['first']+' / '+str(j+1),
                text=self.case['sus'][i]['name']+'\n\nQ: '+question+'\n\nA: '+answer+'\n\nRecorded statement. Verify it against independent evidence.',
                src='TALK',subj=i,kind='ctx',anchor=('room',(i,j)),found=True))
            history[j]=eid
        self.room_answer=self.case['ev'][history[j]]['text']
        self.room_view='answer';self.desk_scroll=0
        self.snd('click')

    def room_transcript(self):
        ids=self.case['room_history'].get(self.room_person,{})
        self.room_answer='\n\n'.join(self.case['ev'][eid]['text'] for eid in ids.values()) or 'No questions asked yet. Return to the questions to begin.'
        self.room_view='answer';self.desk_scroll=0

    def draw_interrogation(self,s,mouse):
        def text(t,x,y,col=TXT,f=None):s.blit((f or F2).render(t,True,col),(x,y))
        def button(rect,label,fn,en=True):
            r=pygame.Rect(rect);hover=en and r.collidepoint(mouse)
            pygame.draw.rect(s,(46,69,68) if hover else PANEL2,r,border_radius=3)
            pygame.draw.rect(s,ACC if hover else LINE,r,1,border_radius=3)
            text(fit(label,F1,r.w-12),r.x+6,r.y+7,TXT if en else DIM,F1)
            if en:self.desk_buttons.append((r,fn))
        # Fixed standing viewpoint: two side walls, back wall and tiled floor.
        s.fill((18,24,28))
        pygame.draw.polygon(s,(78,88,85),[(0,28),(78,62),(78,182),(0,243)])
        pygame.draw.polygon(s,(62,73,73),[(400,28),(322,62),(322,182),(400,243)])
        pygame.draw.rect(s,(90,101,96),(78,62,244,121))
        pygame.draw.polygon(s,(47,57,57),[(0,243),(78,182),(322,182),(400,243)])
        pygame.draw.polygon(s,(48,58,60),[(0,28),(400,28),(322,62),(78,62)])
        for x in range(-100,501,60):pygame.draw.line(s,(68,77,73),(200+(x-200)//3,182),(x,243))
        for y in (192,209,230):pygame.draw.line(s,(68,77,73),(0,y),(400,y))
        # Observation glass, sealed door, wall clock and overhead light.
        pygame.draw.rect(s,(36,44,45),(91,83,79,55))
        pygame.draw.rect(s,(147,155,149),(91,83,79,55),3)
        pygame.draw.line(s,(61,79,79),(97,127),(155,89),3)
        pygame.draw.rect(s,(56,65,65),(269,78,40,104))
        pygame.draw.rect(s,(126,135,127),(269,78,40,104),2)
        pygame.draw.rect(s,(23,34,37),(278,91,22,28))
        pygame.draw.line(s,(182,183,157),(291,139),(301,139),2)
        pygame.draw.circle(s,(217,216,188),(222,87),12)
        pygame.draw.circle(s,(48,60,60),(222,87),12,1)
        pygame.draw.line(s,(48,60,60),(222,87),(222,79),1)
        pygame.draw.line(s,(48,60,60),(222,87),(228,90),1)
        pygame.draw.polygon(s,(182,189,174),[(156,42),(244,42),(259,52),(143,52)])
        pygame.draw.line(s,(241,238,199),(153,50),(249,50),3)
        pygame.draw.rect(s,(29,37,39),(309,67,12,7),border_radius=2)
        pygame.draw.circle(s,RED,(312,70),1)
        text('INTERVIEW 02',95,67,DIM,F1)
        # Suspect's chair and seated figure behind the fixed table.
        pygame.draw.rect(s,(35,44,47),(177,119,49,72),border_radius=6)
        for x in (179,223):pygame.draw.line(s,(29,35,37),(x,171),(x,200),3)
        if self.room_person is not None:
            p=self.case['sus'][self.room_person]
            pygame.draw.polygon(s,p['col'],[(175,177),(178,140),(190,131),(213,131),(226,142),(230,177)])
            pygame.draw.rect(s,p['skin'],(195,125,13,14))
            pygame.draw.ellipse(s,p['skin'],(185,100,31,33))
            pygame.draw.ellipse(s,p['hair'],(184,97,33,17))
            for ex in (193,207):pygame.draw.rect(s,(25,31,30),(ex,115,3,2))
            pygame.draw.line(s,(111,77,63),(196,125),(205,125))
        # Table projects toward the viewer; bolted legs, recorder and evidence folder.
        pygame.draw.polygon(s,(120,126,114),[(143,168),(260,168),(309,218),(96,218)])
        pygame.draw.polygon(s,(66,76,74),[(96,218),(309,218),(309,225),(96,225)])
        for x in (112,293):
            pygame.draw.line(s,(38,47,47),(x,223),(x,242),5)
            pygame.draw.ellipse(s,(101,108,100),(x-7,237,14,5))
        pygame.draw.rect(s,(28,34,35),(227,185,24,15),border_radius=2)
        pygame.draw.circle(s,RED,(231,188),1)
        for x in range(236,248,3):pygame.draw.line(s,DIM,(x,189),(x,195))
        pygame.draw.polygon(s,(188,167,119),[(140,185),(176,185),(182,204),(133,204)])
        pygame.draw.line(s,(60,73,70),(138,193),(172,193))
        if self.room_person is not None:
            p=self.case['sus'][self.room_person]
            pygame.draw.ellipse(s,p['skin'],(175,173,17,6))
            pygame.draw.ellipse(s,p['skin'],(213,173,17,6))
        # Detective's near chair: the viewer is standing behind it.
        pygame.draw.rect(s,(26,36,38),(180,226,49,19),border_radius=5)
        button((8,27,112,26),'BACK TO DESK',lambda:self.enter_desk('desk'))
        button((265,27,127,26),'CHOOSE SUSPECT',lambda:self.change_room_suspect())
        pygame.draw.rect(s,(12,21,25),(0,245,400,175))
        if self.room_person is None:
            text('Who would you like to question?',12,251,AMB)
            text('Choosing a person does not accuse them.',12,271,DIM,F1)
            for i,p in enumerate(self.case['sus']):
                x=8+(i%2)*196;y=290+(i//2)*39
                button((x,y,188,33),p['name']+' / '+p['role'],lambda i=i:self.seat_suspect(i))
        elif self.room_view=='questions':
            p=self.case['sus'][self.room_person]
            text(fit(p['name']+' / '+p['role'],F2,374),12,249,AMB)
            self.desk_max=max(0,len(self.room_questions())*36-111)
            self.desk_scroll=clamp(self.desk_scroll,0,self.desk_max)
            s.set_clip((8,270,384,111))
            for j,(question,answer,required) in enumerate(self.room_questions()):
                enabled=required is None or self.case['ev'][required]['found']
                label=question if enabled else 'Find exhibit: '+self.case['ev'][required]['title']
                button((8,270+j*36-int(self.desk_scroll),384,32),label,lambda j=j:self.ask_in_room(j),enabled)
            s.set_clip(None)
            self.desk_buttons=[(r.clip(pygame.Rect(8,270,384,111)),fn) if r.y>=270 else (r,fn) for r,fn in self.desk_buttons]
            button((8,389,384,25),'REVIEW SAVED TRANSCRIPT',self.room_transcript)
        else:
            text('RECORDED ANSWER / scroll to read',12,250,AMB)
            lines=wrap(self.room_answer,F2,366)
            self.desk_max=max(0,len(lines)*17-108)
            self.desk_scroll=clamp(self.desk_scroll,0,self.desk_max)
            s.set_clip((12,273,376,108))
            for j,line in enumerate(lines):text(line,16,273+j*17-self.desk_scroll,TXT)
            s.set_clip(None)
            button((8,389,384,25),'ASK ANOTHER QUESTION',lambda:self.room_more_questions())

    def change_room_suspect(self):
        self.room_person=None;self.room_view='choose';self.desk_scroll=0

    def room_more_questions(self):
        self.room_view='questions';self.desk_scroll=0

    def open_profile(self,i):
        self.profile=i;self.desk_scroll=0;self.mark_comparison('web',i)
        self.sync_keyboard()

    def open_browser(self):
        self.laptop_browser=True;self.profile=None;self.desk_scroll=0
        self.sync_keyboard()

    def open_device(self,i):
        self.desktop=None;self.device_index=i
        self.go('device',push=False,tab='home')

    def return_drawer(self):
        self.go('home',push=False)
        self.enter_desk('drawer')

    def read_device(self,i):
        self.sub['tab']='activity';self.scroll=0;self.mark_comparison('device',i)

    def read_device_messages(self,i):
        self.sub['tab']='messages';self.scroll=0;self.mark_comparison('message',i)

    def d_device(self):
        self.tile_back();p=self.case['sus'][self.device_index]
        self.header(p['first'].upper()+"'S PHONE")
        tab=self.sub.get('tab','home')
        if tab=='home':
            self.text('SECURED CASE EXHIBIT',8,35,AMB)
            draw_portrait(self.S,pygame.Rect(67,55,64,72),p)
            self.text(p['name'],99,135,TXT,center=True)
            self.text('Archived handset / read only',99,150,DIM,center=True)
            for j,(key,label,fn) in enumerate([
                ('msg','Messages',lambda:self.read_device_messages(self.device_index)),
                ('photos','Photos',lambda:self.sub.update(tab='photos')),
                ('call','Activity',lambda:self.read_device(self.device_index))]):
                x=7+j*63
                self.btn((x,176,58,65),'',fn)
                draw_icon(self.S,key,pygame.Rect(x+13,182,32,32))
                self.text(label,x+29,221,TXT,center=True)
            self.text('Put down to return to the drawer',99,260,DIM,center=True)
            return
        if tab=='photos':
            draw_portrait(self.S,pygame.Rect(42,45,114,132),p)
            self.para('Saved portrait / '+fmt(self.case['T']-40)+'\nThe investigation phone holds the zoomable evidence copy.',8,190,182,DIM)
            return
        if tab=='activity':
            content=self.case['device_logs'][self.device_index]
        else:
            content=self.case['device_messages'][self.device_index]
        def draw(y,w):return self.para(content,7,y,w-9,TXT)-y
        self.scrollv((0,35,SW,211),draw)
        if tab=='activity':
            self.btn((6,253,186,25),'READ CHANGEOVER MESSAGE',lambda:self.read_device_messages(self.device_index))
        elif self.difficulty=='Experienced':
            self.btn((6,253,90,25),'ACTIVITY',lambda:self.read_device(self.device_index))
            self.btn((102,253,90,25),'SEARCH',lambda:self.open_message_search(self.device_index))
        else:
            self.btn((6,253,186,25),'BACK TO ACTIVITY',lambda:self.read_device(self.device_index))

    def save_thread_pin(self,key):
        ex=self.case['expert'];saved=ex.setdefault('threads',{})
        if key not in saved:
            thread=self.case['threads'][key]
            saved[key]=self.expert_evidence('Messages / '+key,'\n\n'.join(m['t']+' / '+m['x'] for m in thread['msgs']),'MSG',thread['sus'])
        self.find(saved[key]);self.board_pin(saved[key]);self.toast('Thread pinned to your board')

    def expert_evidence(self,title,text,src,person=None):
        eid=len(self.case['ev'])
        self.case['ev'].append(dict(id=eid,title=title,text=text,src=src,subj=person,kind='ctx',anchor=None,found=False))
        return eid

    def setup_experienced(self):
        c=self.case
        ex=c['expert']=dict(details=[],claims=[],replies=[],board=[],connections=[],selected=None,mode='move',picker=False,
                          next_event=self.now+random.uniform(70,120),drawer_open=False,wake_until=0,notice_until=0)
        labels=['Reflection','Receipt','Clock face','Muddy shoes','Background object']
        for i,p in enumerate(c['sus']):
            # These photographs predate the incident and never override its unique solution.
            early=fmt(c['T']-40)
            facts=[f'A reflection shows a parcel trolley marked BAY {i+1}. A reflection does not establish who used it.',
                   f'A paper receipt reads ANNEX / {early} / locker {i+1}. It may have been carried from elsewhere.',
                   f'The wall clock reads {fmt(c["T"]-47)}; the photo archive is stamped {early} station time. These clocks disagree.',
                   'Dried pale mud covers the soles. A background sign says COURTYARD REPAIRS; the same soil is used in several areas.',
                   f'A case marked LOAN {i+1} is behind the chair. Ownership cannot be inferred from proximity.']
            details=[]
            for j,label in enumerate(labels):
                eid=self.expert_evidence(label+' / '+p['first'],facts[j]+' Photo taken before the incident; compare other records.','PHOTO',i)
                details.append(dict(label=label,text=facts[j],eid=eid))
            ex['details'].append(details)
            claims=['There were no deliveries near me when that portrait was taken.',
                    'I had not handled any annex paperwork before the portrait.',
                    'I used the wall clock; it always matched station time.',
                    'My shoes stayed clean all evening.',
                    'There was no borrowed equipment near my chair.']
            replies=['That trolley was there. I had forgotten the delivery. Search my messages for parcel; the handover note says who could use it.',
                     'I did handle that receipt. I collected it for someone else. Search my messages for annex; check the wording before assuming I visited.',
                     'Then my clock assumption was wrong. Search my messages for clock. Use the technician correction for the scene logger, not this wall clock.',
                     'You are right about the mud. I crossed the repair area earlier. Search courtyard in my messages; it was a shared route.',
                     'I remember the case now. It was waiting to be collected. Search loan in my messages; a nearby object is not proof of ownership.']
            ex['claims'].append(claims[i%5]);ex['replies'].append(replies[i%5])
            c['device_messages'][i]+=(f'\n\nEarlier service exchange, {fmt(c["T"]-55)} station time:\n'
                f'Parcel desk: Bay {i+1} trolley is shared by the shift.\n'
                f'Annex clerk: Keep the locker {i+1} receipt for collection; the carrier need not visit the annex.\n'
                'Maintenance: The portrait wall clock runs seven minutes slow. The scene logger has its own separate correction.\n'
                'Groundskeeper: Courtyard repairs use pale soil also stocked beside the loading area.\n'
                f'Stores: Loan {i+1} may be left behind the portrait chair pending collection.')
            # Keep the collected archive and searchable handset consistent.
            c['ev'][c['artifacts']['device'][i]]['text']=c['device_logs'][i]+'\n\n'+c['device_messages'][i]
        which=random.randrange(3)
        ex['audio_kind']=['bell_clue','machine_clue','train_clue'][which]
        ex['audio_caption']=['Two clear bells, spaced about a second apart.','A low motor pulses on and off in a regular rhythm.','A rising then falling platform chime over a low rumble.'][which]
        ex['audio_place']=['Annex reception','Loading workshop','Station concourse'][which]
        ex['audio_person']=random.randrange(len(c['sus']))
        ex['audio_eid']=self.expert_evidence('Recovered voicemail / background sound',
            f'Recorded {fmt(c["T"]-50)} station time. '+ex['audio_caption']+' A recording can be replayed elsewhere; compare context.','AUDIO',ex['audio_person'])
        ex['sound_memo']=self.expert_evidence('Facilities sound reference',
            'Annex reception: two bells about a second apart. Loading workshop: pulsing motor. Station concourse: rising then falling platform chime. Sounds can carry through open doors or be replayed. This reference does not locate a person by itself.','DOC')
        self.conversation_query=''

    def open_message_search(self,person):
        self.conversation_query='';self.go('msgsearch',person=person);self.sync_keyboard()

    def d_msgsearch(self):
        self.tile_back();self.header('SEARCH MESSAGES')
        self.btn((5,32,188,24),self.conversation_query or 'Type a place, date or phrase',self.sync_keyboard)
        person=self.sub.get('person');query=self.conversation_query.casefold().strip()
        rows=[]
        if person is None:
            for key,thread in self.case['threads'].items():
                for msg in thread['msgs']:
                    if query and query in (msg['x']+' '+msg['t']).casefold():rows.append((key,msg['t']+' / '+msg['x'],lambda k=key:self.open_thread(k)))
        else:
            for paragraph in self.case['device_messages'][person].split('\n'):
                if query and query in paragraph.casefold():rows.append((self.case['sus'][person]['first'],paragraph,lambda:self.go('device',tab='messages')))
        def draw(y,w):
            top=y
            for name,content,fn in rows:
                lines=wrap(name+': '+content,F1,w-18);h=len(lines)*12+12
                self.btn((5,y,w-10,h),'',fn)
                self.para(name+': '+content,10,y+5,w-20,TXT);y+=h+6
            if not rows:y=self.para('Enter a phrase found in another clue.' if not query else 'No matching messages. Try a shorter phrase. Search does not identify the culprit.',8,y,w-16,DIM)
            return y-top
        self.scrollv((0,64,SW,185),draw)
        self.btn((5,258,188,22),'BACK TO CONVERSATIONS',lambda:self.go('msg' if person is None else 'device',tab='messages'))

    def d_secrets(self):
        self.tile_back();self.header('PHOTO DETAILS')
        i=self.sub['person'];focus=self.sub.get('focus',0);z=self.sub.get('zoom',1)
        details=self.case['expert']['details'][i]
        photo=pygame.Surface((176,150));photo.fill((53,60,58))
        pygame.draw.rect(photo,(88,77,61),(0,105,176,45))
        draw_portrait(photo,pygame.Rect(60,36,60,95),self.case['sus'][i])
        # Five objects live in the same original image; zoom crops these actual pixels.
        rects=[pygame.Rect(5,12,35,44),pygame.Rect(10,96,37,32),pygame.Rect(132,8,32,32),pygame.Rect(65,128,45,18),pygame.Rect(130,91,36,39)]
        pygame.draw.rect(photo,(143,169,170),rects[0]);pygame.draw.rect(photo,(33,44,49),rects[0],2)
        pygame.draw.line(photo,(216,226,214),(8,16),(36,45));photo.blit(F1.render('BAY '+str(i+1),True,(23,35,38)),(7,35))
        pygame.draw.rect(photo,(232,219,178),rects[1]);photo.blit(F1.render('ANNEX',True,(30,29,24)),(11,98));photo.blit(F1.render(fmt(self.case['T']-40),True,(30,29,24)),(11,111))
        pygame.draw.circle(photo,(227,218,187),(148,24),15);pygame.draw.circle(photo,(24,35,33),(148,24),15,1)
        minutes=(self.case['T']-47)%60;hour=((self.case['T']-47)/60)%12
        for angle,length in ((minutes*math.tau/60,12),(hour*math.tau/12,8)):
            pygame.draw.line(photo,(24,35,33),(148,24),(148+int(math.sin(angle)*length),24-int(math.cos(angle)*length)),2)
        for x in (66,90):
            pygame.draw.ellipse(photo,(25,29,28),(x,129,20,14));pygame.draw.line(photo,(170,153,113),(x+2,140),(x+17,140),3)
        pygame.draw.rect(photo,(37,51,48),rects[4],border_radius=3);pygame.draw.rect(photo,(170,165,120),(137,87,20,7),2)
        photo.blit(F1.render('LOAN',True,TXT),(133,103));photo.blit(F1.render(str(i+1),True,AMB),(143,115))
        crop=pygame.Rect(0,0,176//z,150//z);crop.center=rects[focus].center;crop.clamp_ip(photo.get_rect())
        self.S.blit(pygame.transform.scale(photo.subsurface(crop),(176,150)),(11,51))
        for j,r in enumerate(rects):
            target=pygame.Rect(11+(r.x-crop.x)*z,51+(r.y-crop.y)*z,r.w*z,r.h*z).clip(pygame.Rect(11,51,176,150))
            if target.w and target.h:
                self.btns.append((target,lambda j=j:self.inspect_secret(i,j)))
                if j==focus:pygame.draw.rect(self.S,AMB,target,1)
        self.text('ARCHIVE '+fmt(self.case['T']-40)+' / '+str(z)+'x',10,34,DIM)
        self.btn((5,207,34,22),'<',lambda:self.sub.update(focus=(focus-1)%5))
        self.btn((43,207,110,22),details[focus]['label'],lambda:self.sub.update(zoom=2 if z==1 else 4 if z==2 else 1))
        self.btn((157,207,36,22),'>',lambda:self.sub.update(focus=(focus+1)%5))
        self.para('Tap the label to zoom, then the object to collect. Read its full exhibit in Evidence.',7,235,184,DIM)
        self.btn((5,264,188,18),'BACK TO PORTRAIT',lambda:self.go('photos',person=i,zoom=1))

    def inspect_secret(self,i,j):
        if self.sub.get('zoom',1)<2:self.sub.update(focus=j,zoom=2);return
        self.find(self.case['expert']['details'][i][j]['eid'])
        self.toast('Detail saved in Evidence')

    def d_audio(self):
        self.tile_back();self.header('AUDIO INVESTIGATION');ex=self.case['expert']
        p=self.case['sus'][ex['audio_person']]
        self.para('Voicemail / '+p['name']+'\nStation time '+fmt(self.case['T']-50)+'\n\n"It is '+p['first']+'. I left the envelope by the counter. Please keep it for collection."',7,35,184,TXT)
        self.btn((7,130,184,24),'REPLAY BACKGROUND AUDIO',self.play_expert_audio)
        self.btn((7,159,184,22),'READ SOUND REFERENCE',lambda:self.find(ex['sound_memo']))
        if self.case['ev'][ex['audio_eid']]['found']:
            self.para('Sound captions: '+ex['audio_caption'],7,189,184,AMB)
        self.para('Compare the recording with the facilities reference in Evidence. This earlier call does not prove location at the incident.',7,231,184,DIM)

    def play_expert_audio(self):
        ex=self.case['expert'];self.snd(ex['audio_kind'],.8);self.find(ex['audio_eid'])
        self.say(ex['audio_caption'],AMB)

    def update_desk_events(self):
        ex=self.case.get('expert')
        if not ex or self.desktop is None or self.guide or self.now<ex['next_event']:return
        ex['next_event']=self.now+random.uniform(90,170)
        event=random.randrange(3)
        if event==0:ex['drawer_open']=True;notice='A faint scrape comes from the desk drawer.'
        elif event==1:ex['wake_until']=self.now+45;notice='The laptop wakes without being touched.'
        else:self.snd('knock',.45);notice='Three quiet knocks. Nobody answers.'
        ex['notice']=notice;ex['notice_until']=self.now+7

    def board_pin(self,eid=None):
        ex=self.case['expert'];pins=ex['board']
        if eid is not None:
            if any(p.get('eid')==eid for p in pins):return
            item=self.case['ev'][eid];title=item['title'];body=item['text']
        else:
            title='My note';body=self.notebooks[self.note_key].strip()
            if not body:self.toast('Write a notebook note first');return
        pins.append(dict(eid=eid,title=title,text=body,x=15+(len(pins)%3)*125,y=80+(len(pins)%4)*45))
        ex['picker']=False;ex['selected']=len(pins)-1

    def board_unpin(self):
        ex=self.case['expert'];j=ex['selected']
        if j is None:return
        ex['board'].pop(j)
        ex['connections']=[[a-(a>j),b-(b>j)] for a,b in ex['connections'] if j not in (a,b)]
        ex['selected']=None

    def board_select(self,j):
        ex=self.case['expert'];old=ex['selected']
        if ex['mode']=='connect' and old is not None and old!=j:
            pair=sorted([old,j])
            if pair in ex['connections']:ex['connections'].remove(pair)
            else:ex['connections'].append(pair)
        ex['selected']=j;self.desk_scroll=0

    def board_place(self,point):
        ex=self.case['expert'];j=ex['selected']
        if j is not None and ex['mode']=='move':
            ex['board'][j].update(x=clamp(point[0]-52,8,286),y=clamp(point[1]-22,78,234))

    def draw_board(self,s,mouse):
        ex=self.case['expert'];pins=ex['board']
        def text(t,x,y,col=TXT):s.blit(F1.render(t,True,col),(x,y))
        def button(r,label,fn):
            r=pygame.Rect(r);pygame.draw.rect(s,PANEL2,r);pygame.draw.rect(s,ACC,r,1)
            text(label,r.x+4,r.y+8);self.desk_buttons.append((r,fn))
        s.fill((69,51,35));text('YOUR EVIDENCE BOARD / NO AUTOMATIC VERDICT',9,9,AMB)
        button((8,28,82,28),'+ EXHIBIT',lambda:ex.update(picker=not ex['picker']))
        button((95,28,66,28),'+ NOTE',lambda:self.board_pin())
        button((166,28,78,28),ex['mode'].upper(),lambda:ex.update(mode='connect' if ex['mode']=='move' else 'move'))
        button((249,28,72,28),'UNPIN',self.board_unpin)
        button((326,28,66,28),'DESK',lambda:self.enter_desk('desk'))
        if ex['picker']:
            found=[e for e in self.case['ev'] if e['found']]
            self.desk_max=max(0,len(found)*35-320);self.desk_scroll=clamp(self.desk_scroll,0,self.desk_max)
            s.set_clip((8,72,384,320))
            for j,e in enumerate(found):
                r=pygame.Rect(9,74+j*35-self.desk_scroll,380,30)
                if r.bottom>72 and r.top<392:button(r,fit(e['title'],F1,368),lambda eid=e['id']:self.board_pin(eid))
            s.set_clip(None)
            self.desk_buttons=[(r.clip(pygame.Rect(8,72,384,320)) if r.y>=60 else r,fn) for r,fn in self.desk_buttons]
            return
        text('MOVE: select pin, tap empty space. CONNECT: select two pins.',8,62)
        self.desk_buttons.append((pygame.Rect(8,78,384,210),lambda:self.board_place(getattr(self,'board_pointer',mouse))))
        for a,b in ex['connections']:
            pa,pb=pins[a],pins[b]
            pygame.draw.line(s,(184,63,51),(pa['x']+52,pa['y']+22),(pb['x']+52,pb['y']+22),2)
        for j,p in enumerate(pins):
            r=pygame.Rect(p['x'],p['y'],106,44);pygame.draw.rect(s,(222,211,171),r)
            pygame.draw.rect(s,ACC if j==ex['selected'] else (72,62,48),r,2)
            pygame.draw.circle(s,(173,53,47),(r.centerx,r.top+4),3)
            eid=p.get('eid');item=self.case['ev'][eid] if eid is not None else None
            portrait=item is not None and item['src']=='PHOTO' and item['subj'] is not None
            if portrait:draw_portrait(s,pygame.Rect(r.x+3,r.y+10,22,29),self.case['sus'][item['subj']])
            offset=28 if portrait else 5
            for k,line in enumerate(wrap(p['title'],F1,103-offset)[:3]):text(line,r.x+offset,r.y+9+k*10,(31,42,39))
            self.desk_buttons.append((r,lambda j=j:self.board_select(j)))
        selected=ex['selected'];content='Pin found photos, messages or other exhibits. + NOTE pins a copy of your current notebook page. Connections are your hypotheses; tap a connected pair again to remove its thread.' if selected is None else pins[selected]['text']
        lines=wrap(content,F1,374);self.desk_max=max(0,len(lines)*12-100);self.desk_scroll=clamp(self.desk_scroll,0,self.desk_max)
        pygame.draw.rect(s,(15,24,26),(5,299,390,103));s.set_clip((8,300,384,100))
        for j,line in enumerate(lines):text(line,10,302+j*12-self.desk_scroll)
        s.set_clip(None)

    def pip_available(self):
        return bool(self.difficulty!='Experienced' and self.case and (self.desktop is not None or self.scr in APPS or self.scr=='brief') and not (self.hack or self.scare or self.incoming))

    def pip_hints(self):
        c=self.case
        if not c['ev'][c['incident_ev']]['found']:
            step='Start with the scene log. On your investigation phone open Inspect. Use the room arrows to reach '+c['R']+'. Tap Incident log, then READ FULL EXHIBIT. It contains the time, access group, device identifier and physical method.'
        elif not c['ev'][c['clock_ev']]['found']:
            step='You found the scene log! Now open Messages on your investigation phone and read the technician message in the '+c['wit']+' conversation. It tells you how to correct the logger time.'
        elif not c['photo_seen']:
            step='You have the log and clock message. Next open Photos, choose a portrait, zoom to 2x and tap the badge. Read the saved exhibit and compare its code with the scene access group.'
        elif not (c['device_seen'] & c['message_seen']):
            step='Next check a suspect handset. PUT DOWN > drawer > a phone. Read Activity AND Messages on the SAME phone. The service message says when the replacement group starts. Decide which group applied at the corrected crime time.'
        elif not c['web_seen']:
            step='Next check travel. PUT DOWN > laptop > Google. Search a suspect name. Add their minimum journey time to their public check-in time. Compare their earliest possible arrival with the corrected crime window.'
        else:
            step='You have started all three checks. Compare each person: badge code, device group active at the crime time, and possible arrival time. Investigate any missing entries. When one person fits all three, select their portrait, handset archive and public entry in Accuse.'
        context={
            'device':'This is a suspect handset. Activity lists the groups. Messages contains the changeover time. The message SENT time is different from the time the replacement starts. Read both views; the arrow returns to this handset home.',
            'accuse':'Collected exhibits for your selected suspect load automatically. Tap missing rows to find them. EXPLAIN asks for the corrected incident window and physical method. Read Scene instrument log in Evidence for the method. Other suspicious clues cannot replace those three exhibits.',
            'photos':'Select a person, press + to zoom, then tap their badge to collect the portrait exhibit. A shared badge code is only one part of the case.',
            'insp':'Use the arrows to reach the scene named in the brief. Tap Incident log and READ FULL EXHIBIT. You can reread it in Evidence after collection.',
            'msg':'Read the technician note for the scene clock correction. Device replacement messages are on each suspect handset in the desk drawer, not this investigation phone.',
            'foot':'Pick a camera, play a clip, and use the time controls to replay it. An earlier visit does not prove the person committed the crime.',
            'print':'Compare prints, but also read handling history. An old or partial print is not enough to accuse someone.',
            'evid':'Open ACCUSATION FOLDERS to see each suspect and their three required exhibits and missing items. Tap an exhibit and scroll its complete text. Your scene log, technician message and collected individual suspect records are stored here.'}
        desks={
            'desk':'Click the handset to pick up your investigation phone. The drawer contains suspect phones. The laptop searches public profiles. The notebook is for your own notes.',
            'drawer':'Choose a suspect phone. Read its Activity and Messages, then PUT DOWN returns you to this drawer.',
            'laptop':'Open Google from the laptop home page, type a suspect name and open their profile. Add the check-in time and minimum journey duration to find their earliest possible arrival.',
            'notebook':'Write one line per suspect: badge / device group at crime time / earliest arrival. Notes save automatically. You can leave a question mark until you find the missing clue.',
            'interrogation':'Choose a suspect and ask questions. Their answers are claims: check them against collected exhibits. Selecting a person here is not an accusation.',
            'board':'Pin collected exhibits and your notebook notes. MOVE repositions pins; CONNECT joins two selected pins. These connections record your own ideas and do not score guilt.'}
        here=desks.get(self.desktop) if self.desktop else context.get(self.scr)
        return [('NEXT STEP',step),('WHERE YOU ARE',here or 'Use your investigation phone to inspect the scene and read evidence. PUT DOWN opens the desk. The circle returns home; the arrow goes back.'),
                ('CORRECT THE CLOCK','Read the technician message. If the scene logger is behind station time, ADD the difference. If it is ahead, SUBTRACT it. Example: 9:10 on a logger six minutes behind becomes 9:16. Correct both ends of the logged window. Do not adjust phone or public timestamps already in station time.'),
                ('PREVIOUS OR REPLACEMENT?','Read the changeover time in that suspect handset Messages. BEFORE that minute, use the previous group. AT that minute and AFTER, use the replacement. Compare the applicable group with the scene device identifier. Several people may match; this is not a verdict.'),
                ('CHECK THE JOURNEY','Add minimum travel time to the public check-in time. Example: 8:50 plus 20 minutes means earliest arrival 9:10. If the crime window ended at 9:05, that trip cannot fit. Arriving in time only means the person had an opportunity.'),
                ('HOW TO FINISH','Choose one person whose badge, active device group and travel timing all fit. In Accuse select that person. Their collected Portrait, Handset archive and Public entry load automatically. Tap any missing row to find it. Then EXPLAIN: choose the corrected time window and the method described by the scene log. Pip does not select a culprit for you.')]

    def toggle_pip(self):
        self.pip_open=not self.pip_open;self.pip_page=0
        if self.pip_open:
            self.touch_gesture=None;self.down=False
            if self.mobile:pygame.key.stop_text_input();self.keyboard_target=None
        else:self.sync_keyboard()

    def draw_corner_pip(self):
        self.pip_buttons=[]
        if not self.pip_available():return
        W,H=self.win.get_size()
        scale=max(.5,min(2.5,(W-16)/216,(H-24)/248))
        def retro_blit(surface,pos,size):
            # Use the same small canvas and softened pixel scaling as the game.
            enlarged=pygame.transform.scale(surface,(surface.get_width()*3,surface.get_height()*3))
            self.win.blit(pygame.transform.smoothscale(enlarged,size),pos)
        badge=pygame.Surface((40,40));badge.fill((8,16,20))
        pygame.draw.rect(badge,LINE,(0,0,40,40),1)
        pygame.draw.line(badge,ACC,(2,2),(37,2))
        pygame.draw.line(badge,(44,72,69),(2,3),(2,37))
        self.bot_sprite(badge,4,7)
        badge.blit(F1.render('PIP',True,AMB),(12,29))
        size=max(1,int(40*scale));r=pygame.Rect(W-size-8,8,size,size)
        retro_blit(badge,r.topleft,r.size)
        self.pip_buttons.append((r,self.toggle_pip))
        if not self.pip_open:return
        canvas=pygame.Surface((216,202));canvas.fill((8,17,21))
        pygame.draw.rect(canvas,(60,89,84),(0,0,216,202),1)
        pygame.draw.rect(canvas,LINE,(3,3,210,196),1)
        pygame.draw.rect(canvas,(23,43,44),(5,5,206,22))
        pygame.draw.line(canvas,ACC,(6,27),(209,27))
        pages=[];lineheight=F1.get_linesize()+2
        capacity=max(1,128//lineheight)
        for title,body in self.pip_hints():
            lines=wrap(body,F1,194)
            for start in range(0,len(lines),capacity):pages.append((title,lines[start:start+capacity]))
        self.pip_page=int(clamp(self.pip_page,0,len(pages)-1));title,lines=pages[self.pip_page]
        canvas.blit(F1.render('PIP / '+title,True,AMB),(10,11))
        for j,line in enumerate(lines):canvas.blit(F1.render(line,True,TXT),(11,35+j*lineheight))
        canvas.blit(F1.render('HELP ARCHIVE  %02d/%02d' % (self.pip_page+1,len(pages)),True,DIM),(11,164))
        local_buttons=[]
        for j,(label,fn) in enumerate([('< PREV',lambda:setattr(self,'pip_page',max(0,self.pip_page-1))),('NEXT >',lambda:setattr(self,'pip_page',min(len(pages)-1,self.pip_page+1))),('CLOSE',self.toggle_pip)]):
            rect=pygame.Rect(8+j*68,178,64,17)
            pygame.draw.rect(canvas,PANEL2,rect)
            pygame.draw.rect(canvas,LINE,rect,1)
            pygame.draw.line(canvas,ACC,(rect.x+1,rect.y+1),(rect.right-2,rect.y+1))
            im=F1.render(label,True,TXT);canvas.blit(im,im.get_rect(center=rect.center))
            local_buttons.append((rect,fn))
        # Very faint static scan lines keep the lettering readable.
        scan=pygame.Surface((216,202),pygame.SRCALPHA)
        for y in range(0,202,3):pygame.draw.line(scan,(0,0,0,12),(0,y),(215,y))
        canvas.blit(scan,(0,0))
        width,height=int(216*scale),int(202*scale)
        panel=pygame.Rect(W-width-8,r.bottom+6,width,height)
        retro_blit(canvas,panel.topleft,panel.size)
        sx,sy=width/216,height/202
        for rect,fn in local_buttons:
            self.pip_buttons.append((pygame.Rect(panel.x+round(rect.x*sx),panel.y+round(rect.y*sy),round(rect.w*sx),round(rect.h*sy)),fn))

    def pip_event(self,e):
        if not self.pip_available():return False
        if getattr(e,'touch',False) and e.type in (pygame.MOUSEBUTTONDOWN,pygame.MOUSEBUTTONUP,pygame.MOUSEMOTION):return self.pip_open
        def activate(pos):
            for r,fn in self.pip_buttons:
                if r.collidepoint(pos):fn();self.render();return True
            return False
        if e.type==pygame.FINGERDOWN:
            W,H=self.win.get_size();pos=(e.x*W,e.y*H)
            if self.pip_open or any(r.collidepoint(pos) for r,fn in self.pip_buttons):
                self.pip_touch=(e.finger_id,pos);return True
        if e.type in (pygame.FINGERMOTION,pygame.FINGERUP) and self.pip_touch:
            if e.finger_id!=self.pip_touch[0]:return True
            if e.type==pygame.FINGERUP:
                W,H=self.win.get_size();pos=(e.x*W,e.y*H);start=self.pip_touch[1];self.pip_touch=None
                if math.dist(start,pos)<20:activate(pos)
            return True
        if e.type==pygame.MOUSEBUTTONDOWN:
            if self.pip_open or any(r.collidepoint(e.pos) for r,fn in self.pip_buttons):self.pip_mouse=True;return True
        if e.type==pygame.MOUSEBUTTONUP:
            captured=self.pip_mouse;self.pip_mouse=False
            if captured or self.pip_open or any(r.collidepoint(e.pos) for r,fn in self.pip_buttons):
                if e.button==1:activate(e.pos)
                self.press_seen=False;self.down=False;return True
        if self.pip_open and e.type in (pygame.KEYDOWN,pygame.TEXTINPUT,pygame.MOUSEWHEEL,pygame.MOUSEMOTION):
            if e.type==pygame.KEYDOWN and e.key in (pygame.K_ESCAPE,getattr(pygame,'K_AC_BACK',1073742094)):self.toggle_pip();self.render()
            return True
        return False

    def bot_sprite(self,s,x,y):
        bob=int(math.sin(self.now*4)*1)
        y+=bob
        pygame.draw.ellipse(s,(14,38,37),(x+1,y+22,25,5))
        pygame.draw.rect(s,(70,115,111),(x+5,y+15,18,9),border_radius=3)
        pygame.draw.rect(s,(168,224,202),(x+1,y+2,26,17),border_radius=5)
        pygame.draw.rect(s,(17,39,44),(x+4,y+5,20,10),border_radius=3)
        mood = 'think' if self.scr in ('evid','accuse','msg','device') else 'happy'
        if self.scr == 'insp' and self.case and self.case['ev'][self.case['incident_ev']]['found']: mood='celebrate'
        blink=int(self.now*3)%17==0
        for ex in (8,18):
            if mood=='celebrate':pygame.draw.lines(s,ACC,False,[(x+ex-1,y+10),(x+ex+1,y+8),(x+ex+3,y+10)])
            else:pygame.draw.rect(s,ACC,(x+ex,y+8,3,1 if blink else 3))
        if mood=='think':
            pygame.draw.line(s,AMB,(x+7,y+6),(x+12,y+7))
            pygame.draw.line(s,ACC,(x+12,y+13),(x+16,y+13))
        else:pygame.draw.lines(s,ACC,False,[(x+11,y+12),(x+13,y+14),(x+16,y+14),(x+18,y+12)])
        pygame.draw.line(s,ACC,(x+14,y+2),(x+14,y-2))
        pygame.draw.circle(s,AMB,(x+14,y-3),2)
        pygame.draw.line(s,(168,224,202),(x+24,y+18),(x+30,y+13),2)

    def guide_hint(self):
        c=self.case
        if self.scr=='home':
            event=next(e for e in c['ev'] if e['id']==c['incident_ev'])
            if not event['found']:return 'I am Pip! Tap me for help. Inspect finds the scene log.',(5,123,45,48)
            if not c['ev'][c['clock_ev']]['found']:return 'Open Messages. Read the technician note about the logger clock.',(5,72,45,48)
            if not bool(c['photo_seen']):return 'Tap Photos. Zoom a badge and click it to collect a clue.',(5,174,45,48)
            if not bool(c['device_seen'] and c['message_seen']):return 'Put me down! Open the drawer and inspect a suspect phone.',None
            if not bool(c['web_seen']):return 'Put down the phone. On the laptop, click Google in the corner.',None
            return 'Read the clues, correct the clock and explain your accusation.',(52,174,45,48)
        if self.scr=='insp':
            if next(e for e in c['ev'] if e['id']==c['incident_ev'])['found']:
                return 'Log saved. Home, then Messages: the technician corrects its clock.', 'home'
            for h in c['insp'][self.sub['room']]:
                if h['name']=='Incident log':
                    r=pygame.Rect(h['rect']).move(6,52)
                    return 'Click this scene log. Note the badge and device identifiers.',r
            return 'Tap the room arrow until you reach '+c['R']+'.',(170,32,22,16)
        if self.scr=='photos':
            if self.sub.get('person') is None:return 'Choose a portrait. Each badge can hide a useful detail.',(4,52,178,38)
            if self.sub.get('zoom',1)==1:return 'Tap + to zoom. Then click the outlined badge!',(61,209,45,22)
            if self.sub['person'] not in c['photo_seen']:
                return 'Click the outlined badge in the enlarged photo.',getattr(self,'photo_target',pygame.Rect(60,100,90,65))
            return 'Clue recorded! Open ALL PHOTOS and inspect the other badges.',(112,209,75,22)
        if self.scr=='device':
            if self.sub.get('tab','home')=='home':return 'Same phone controls! Tap Activity to compare its device group.',(133,176,58,65)
            return 'Read BOTH Messages and Activity. The assignment changes at a set time.',None
        tips={'evid':'Read each exhibit. Compare codes, dates and assignment changes.', 'accuse':'Choose a suspect. Their exhibits load for you; explain the time and method.', 'foot':'Tap a motion clip or drag the timeline to investigate.', 'print':'Compare ridge shape and spacing. Prints alone are not proof.', 'msg':'Read carefully. Messages are hints, not confessions.', 'intr':'Ask about the alibi, then compare independent clues.', 'notes':'These are your suspect marks. The desk notebook accepts writing.'}
        return tips.get(self.scr,'Tap Pip for the full how-to. X hides guidance.'), 'home'

    def guide_pointer(self,s,r):
        # A local arrowhead stays beside the target; it never crosses evidence text.
        r=pygame.Rect(r).clip(s.get_rect())
        if not r.w or not r.h:return
        pygame.draw.rect(s,AMB,r.inflate(4,4),2,border_radius=3)
        x=r.centerx
        if r.top>=15:
            tip=(x,r.top-2);base=r.top-11
        else:
            tip=(x,r.bottom+2);base=r.bottom+11
        pygame.draw.polygon(s,AMB,[tip,(x-5,base),(x+5,base)])

    def draw_phone_guide(self,cv):
        hint,target=self.guide_hint()
        if target == 'home': r=pygame.Rect(86,352,44,24)
        elif target is None: r=pygame.Rect(66,337,84,12)
        else: r=pygame.Rect(target).move(SX,SY)
        self.guide_pointer(cv,r)
        # Pip lives below the screen, so the controls being demonstrated stay clickable.
        pygame.draw.rect(cv,(10,29,31),(SX,CAPY,SW,CAPH))
        self.bot_sprite(cv,SX+2,CAPY+6)
        lines=wrap(hint,F1,140)
        page=int(self.now/7)%max(1,math.ceil(len(lines)/3))
        for j,line in enumerate(lines[page*3:page*3+3]):cv.blit(F1.render(line,True,TXT),(SX+35,CAPY+1+j*10))
        self.navb.append((pygame.Rect(SX,CAPY,32,CAPH),lambda:self.go('howto',push=False,origin='home',page=0)))
        close=pygame.Rect(SX+SW-14,CAPY,14,14)
        cv.blit(F1.render('x',True,AMB),close.topleft)
        self.navb.append((close,lambda:setattr(self,'guide',False)))

    def draw_desk_guide(self,s):
        tips={'interrogation':('Choose a person. Ask questions and bring relevant exhibits.',(8,290,188,33)), 'desk':('Hover to identify objects. Click the drawer or laptop.',(22,328,338,44)),
              'drawer':('Click a handset. It opens just like your investigation phone.',(36,85,77,105)),
              'laptop':('Click Google in the corner to open suspect search.',(298,22,87,68)),
              'notebook':('Type on the ruled page. Your notes save automatically.',(35,110,330,235))}
        hint,r=tips.get(self.desktop,('Keep comparing independent evidence.',(12,12,376,32)))
        if self.desktop=='laptop' and self.laptop_browser:
            hint='Type a name, then click a profile to read their public timeline.';r=(12,58,328,32)
        self.guide_pointer(s,pygame.Rect(r))
        pygame.draw.rect(s,(12,29,31),(0,0,400,21))
        self.bot_sprite(s,2,1)
        s.blit(F1.render(fit(hint,F1,345),True,TXT),(36,5))
        self.desk_buttons.append((pygame.Rect(380,0,20,21),lambda:setattr(self,'guide',False)))
        s.blit(F1.render('x',True,AMB),(385,4))

    # -- settings
    def d_set(self):
        self.tile_back()
        self.header('SETTINGS')
        self.btn((10, 40, 178, 24), 'Sound: %s' % ('OFF (muted)' if self.muted else 'ON'), lambda: self.set_mute(not self.muted))
        self.btn((10, 70, 178, 24), 'Voices: subtitles on Android' if IS_ANDROID else 'Voice lines: %s' % ('ON' if self.tts_on else 'OFF'), lambda: setattr(self, 'tts_on', not self.tts_on), en=not IS_ANDROID)
        self.btn((10, 100, 178, 24), 'Scares: %s' % ('LOW' if self.scare_low else 'NORMAL'), lambda: setattr(self, 'scare_low', not self.scare_low))
        self.text('Subtitles: always ON (bar under the screen)', 10, 134, DIM)
        self.btn((10, 160, 178, 24), 'QUIT TO TITLE', lambda: self.go('title', push=False), col=RED)
        self.para('Touch: tap controls, swipe to scroll. Keyboard: M mute, Esc back.',10,196,178,DIM)
        self.btn((10,240,178,24),'PRIVACY / OFFLINE',lambda:self.go('privacy'))

    # -- endings
    def d_solved(self):
        c = self.case
        self.tile_back()
        self.header('CASE CLOSED')
        s = c['sus'][c['killer']]
        draw_portrait(self.S, pygame.Rect(6, 34, 52, 52), s)
        self.text(s['name'], 64, 38, RED, F2)
        self.text(s['role'], 64, 54, DIM)
        txt = c['solution'] + '\n\nScore: %d' % self.score
        self.para(txt, 6, 96, 186, TXT)
        if self.level >= 5:
            self.btn((20, 250, 158, 24), 'CONTINUE', lambda: self.go('final', push=False), f=F2)
        else:
            self.btn((20, 250, 158, 24), 'NEXT CASE', self.next_case, f=F2)

    def next_case(self):
        self.level += 1
        self.start_case()

    def d_final(self):
        S = self.S
        S.fill((4, 6, 9))
        self.text('ALL CASES CLOSED', 99, 40, ACC, F2, center=True)
        self.para('Five cases resolved. Five lines gone quiet. You set the phone down on the desk.\n\n'
                  'The screen lights up once more: "THANK YOU FOR LISTENING."\n\nThen it goes dark, and for the first time all night, '
                  'nobody is watching you.\n\nFinal score: %d' % self.score, 10, 70, 178, TXT)
        self.btn((20, 220, 158, 24), 'PLAY AGAIN', self.new_game, f=F2)
        self.btn((20, 250, 158, 22), 'TITLE SCREEN', lambda: self.go('title', push=False))

    def d_dead(self):
        c, S, d = self.case, self.S, self.dead
        t = self.now - d['t0']
        kc = c['sus'][c['killer']]['col']
        S.fill((2, 3, 4))
        if t < 1.5:
            self.text('You accused %s.' % d['name'], 99, 130, TXT, center=True)
            self.text('You were wrong.', 99, 146, RED, center=True)
            if t < .1:
                self.say('You were wrong.', RED, voice=True, whisper=True)
        elif t < 6.0:
            q = (t - 1.5) / 4.5
            pygame.draw.rect(S, (10, 16, 16), (10, 40, SW - 20, 180))
            self.text('FRONT CAMERA  REC', 14, 44, RED)
            draw_figure(S, 99, 215, 3.2, (60, 70, 80), True)
            pygame.draw.rect(S, (90, 120, 130), (80, 196, 38, 26))
            draw_figure(S, int(lerp(170, 120, q)), 150, .6 + q * 2.6, kc)
            for _ in range(int(40 + 300 * q)):
                v = random.randint(30, 140)
                S.set_at((random.randint(10, SW - 11), random.randint(40, 219)), (v, v, v))
            self.glitch = max(self.glitch, .1)
            if 2.0 < t < 2.1:
                self.say('I told you not to look.', RED, voice=True, whisper=True)
            if 4.4 < t < 4.5:
                self.say('Now you are part of the case.', RED, voice=True, whisper=True)
        elif t < 6.9:
            draw_face(S, 99, 130, 150 + int((t - 6) * 90), t)
            if t < 6.05:
                self.snd('scare')
            S.fill((200, 20, 20), special_flags=pygame.BLEND_ADD) if int(t * 30) % 3 == 0 else None
        else:
            self.header('CAPTURED')
            kn = c['sus'][c['killer']]
            self.para('The line went dead. The culprit was %s, the %s.\n\nYou reached case %d of 5 with a score of %d.' % (
                kn['name'], kn['role'], self.level, self.score), 10, 40, 178, TXT)
            self.btn((20, 150, 158, 24), 'TRY AGAIN (NEW CASE)', self.start_case, f=F1)
            self.btn((20, 180, 158, 24), 'RESTART FROM CASE 1', self.new_game, f=F1)
            self.btn((20, 210, 158, 22), 'TITLE SCREEN', lambda: self.go('title', push=False))

    # ---------------- overlays
    def draw_overlays(self):
        S = self.S
        b = self.banner
        if b:
            q = min(1.0, (self.now - b['t0']) * 5)
            r = pygame.Rect(6, int(-20 + 34 * q), SW - 12, 20)
            self.btn(r, b['text'], self.open_banner,
                     col=RED, bg=(40, 12, 14))
        inc = self.incoming
        if inc:
            r = pygame.Rect(10, 40, SW - 20, 92)
            pygame.draw.rect(S, (10, 16, 20), r, border_radius=6)
            pygame.draw.rect(S, RED if inc['state'] == 'talk' else ACC, r, 2, border_radius=6)
            self.text(self.case['tips'][inc['contact']]['who'], r.centerx, r.y + 6, TXT, F2, center=True)
            self.text('incoming call' if inc['state'] == 'ring' else 'connected...', r.centerx, r.y + 22, DIM, center=True)
            if inc['state'] == 'ring':
                for k in range(3):
                    pygame.draw.circle(S, ACC, (r.centerx, r.y + 44), 5 + k * 5 + int((self.now * 12) % 5), 1)
                self.btn((r.x + 8, r.y + 66, 70, 20), 'ANSWER', self.answer_call, col=ACC)
                self.btn((r.right - 78, r.y + 66, 70, 20), 'IGNORE', lambda: setattr(self, 'incoming', None), col=RED)
            else:
                pygame.draw.circle(S, RED, (r.centerx, r.y + 50), 4 + int(abs(math.sin(self.now * 8)) * 6), 1)

    def open_banner(self):
        self.banner = None
        if 'Unknown' in self.case['threads']:
            self.open_thread('Unknown')

    def answer_call(self):
        self.incoming['state'] = 'talk'
        self.incoming['t0'] = self.now
        self.glitch = .6
        tip = self.case['tips'][self.incoming['contact']]
        self.say(tip['lines'][0], AMB, voice=True, dur=9)
        if tip not in self.case['calls']:
            self.case['calls'].append(tip)
        self.toast('Call saved in Calls for replay')

    def draw_hack(self):
        h, S = self.hack, self.S
        S.fill((10, 4, 6))
        self.status_bar()
        warn = int(self.now * 6) % 2 == 0
        if h['phase'] == 'warn':
            for _ in range(40):
                pygame.draw.rect(S, (random.randint(0, 255), 0, 0), (random.randint(0, SW), random.randint(0, SH), random.randint(8, 70), 3))
            self.text('ACCESS DENIED', 99, 130, RED if warn else WHITE, F3, center=True)
            return
        pygame.draw.rect(S, (60, 8, 12), (0, 12, SW, 18))
        self.text('!! PHONE HACKED !!', 99, 15, WHITE if warn else RED, F2, center=True)
        kind, st = h['kind'], h['st']
        names = dict(simon='FIREWALL SEQUENCE', nodes='REBOOT NODES', virus='VIRUS PURGE')
        howto = dict(simon='Watch the pads light up, then tap the same pads in the same order.',
                     nodes='Six nodes are scattered on screen. Tap them in order from 1 to 6 before the timer runs out.',
                     virus='Red bugs are crawling over your screen. Tap each one to purge it before the timer runs out.')
        if h['phase'] == 'intro':
            self.text(names[kind], 99, 44, AMB, F2, center=True)
            self.para(howto[kind], 10, 66, 178, TXT)
            self.para('Your apps are locked until you finish. Failing just restarts it. There is no other penalty.', 10, 130, 178, DIM)
            self.btn((30, 190, 138, 26), 'START', self.hack_begin, f=F2)
            return
        if h['phase'] == 'done':
            self.text('ACCESS RESTORED', 99, 130, ACC, F2, center=True)
            return
        self.text(names[kind], 99, 34, AMB, center=True)
        self.text(st.get('msg', ''), 99, 48, TXT, center=True)
        if kind == 'simon':
            lit = st.get('lit')
            cols = [(220, 60, 60), (60, 200, 90), (70, 110, 230), (230, 200, 60)]
            for k in range(4):
                r = pygame.Rect(14 + (k % 2) * 90, 80 + (k // 2) * 70, 80, 62)
                on = lit and lit[0] == k and self.now < lit[1]
                self.btn(r, '', lambda kk=k: self.simon_tap(kk), col=cols[k], bg=cols[k] if on else tuple(q // 4 for q in cols[k]),
                         en=st.get('show') is None)
        elif kind == 'nodes':
            left = max(0, st['end'] - self.now)
            pygame.draw.rect(S, LINE, (10, 62, 178, 6), 1)
            pygame.draw.rect(S, RED if left < 5 else ACC, (11, 63, int(176 * left / 18.0), 4))
            for k, p in enumerate(st['pts']):
                done = k < st['next']
                self.btn((p[0], p[1], 30, 24), str(k + 1), lambda kk=k: self.node_tap(kk), sel=done, col=ACC if done else AMB, f=F2)
        else:
            left = max(0, st['end'] - self.now)
            pygame.draw.rect(S, LINE, (10, 62, 178, 6), 1)
            pygame.draw.rect(S, RED if left < 5 else ACC, (11, 63, int(176 * left / 20.0), 4))
            for b in st['bugs']:
                r = pygame.Rect(int(b[0]), int(b[1]), 22, 18)
                self.btn(r, 'x', lambda bb=b: self.bug_tap(bb), col=RED, bg=(80, 12, 14))

    def simon_tap(self, k):
        st = self.hack['st']
        self.snd('p%d' % k)
        st['lit'] = (k, self.now + .25)
        st['inp'].append(k)
        n = len(st['inp'])
        if st['inp'][-1] != st['seq'][n - 1]:
            self.snd('bad')
            st['seq'] = [random.randrange(4) for _ in range(len(st['seq']))]
            st.update(inp=[], i=0, show=self.now + .8, msg='Wrong! New sequence. Watch...')
        elif n == len(st['seq']):
            self.hack_done()

    def node_tap(self, k):
        st = self.hack['st']
        if k == st['next']:
            st['next'] += 1
            if st['next'] == 6:
                self.hack_done()
        else:
            st['next'] = 0
            st['msg'] = 'Wrong node! Start again from 1.'
            self.snd('bad')

    def bug_tap(self, b):
        st = self.hack['st']
        if b in st['bugs']:
            st['bugs'].remove(b)
            self.snd('glitch')
        if not st['bugs']:
            self.hack_done()

    # ---------------- rendering
    def render_screen(self):
        S = self.S
        self.btns = []
        if self.hack:
            self.draw_hack()
            return
        S.fill(BG)
        self.D[self.scr]()
        if self.scr in APPS:
            self.draw_overlays()
        if self.scr not in ('title', 'dead', 'final'):
            self.status_bar()
        if self.click_fx and self.now - self.click_fx[1] < .3:
            q = (self.now - self.click_fx[1]) / .3
            pygame.draw.circle(S, WHITE, (int(self.click_fx[0][0]), int(self.click_fx[0][1])), int(3 + q * 12), 1)
        if self.scare:
            q = (self.now - self.scare['t0']) / .75
            S.fill((0, 0, 0))
            draw_face(S, 99, 140, int(120 + 140 * q), self.now)
            S.fill((120, 0, 0), special_flags=pygame.BLEND_ADD) if int(self.now * 40) % 2 == 0 else None

    def render(self):
        if self.desktop is not None:
            self.render_desk()
            return
        self.win = pygame.display.get_surface()
        W, H = self.win.get_size()
        mp = self.touch_pos if self.mobile else pygame.mouse.get_pos()
        self.mn = (clamp(mp[0] / float(W) * 2 - 1, -1, 1), clamp(mp[1] / float(H) * 2 - 1, -1, 1))
        sc = min(W / float(CW), H / float(CH)) * .97
        size = (int(CW * sc), int(CH * sc))
        self.sc = size[0] / float(CW)
        self.sc_y = size[1] / float(CH)
        self.ox = (W - size[0]) // 2
        self.oy = (H - size[1]) // 2
        mc = self.to_canvas(mp)
        self.m = (mc[0] - SX, mc[1] - SY)
        if self.bgkey != (W, H):
            self.bgkey = (W, H)
            self.bg = pygame.Surface((W, H))
            for y in range(0, H, 4):
                v = 6 + int(18 * (1 - abs(y / float(H) - .5) * 2))
                pygame.draw.rect(self.bg, (v, v + 4, v + 6), (0, y, W, 4))
            self.fog = pygame.Surface((W * 2, H), pygame.SRCALPHA)
            rr = random.Random(5)
            for _ in range(10):
                pygame.draw.ellipse(self.fog, (120, 150, 150, 14), (rr.randint(0, W * 2), rr.randint(0, H), rr.randint(W // 3, W), rr.randint(H // 8, H // 3)))
            sh = pygame.Surface((CW // 8, CH // 8), pygame.SRCALPHA)
            pygame.draw.rect(sh, (0, 0, 0, 170), (2, 2, CW // 8 - 4, CH // 8 - 4), border_radius=3)
            self.shadow_src = sh
        self.win.blit(self.bg, (0, 0))
        fx = -int((self.now * 8 + self.mn[0] * 20) % W)
        self.win.blit(self.fog, (fx, 0))
        self.win.blit(self.fog, (fx + W, 0))
        # phone body
        cv = self.canvas
        cv.fill((0, 0, 0, 0))
        pygame.draw.rect(cv, (12, 14, 18), (0, 0, CW, CH), border_radius=18)
        pygame.draw.rect(cv, (58, 66, 76), (0, 0, CW, CH), 1, border_radius=18)
        pygame.draw.rect(cv, (26, 32, 38), (2, 2, CW - 4, CH - 4), 1, border_radius=16)
        pygame.draw.rect(cv, (30, 36, 42), (CW // 2 - 14, 5, 28, 3), border_radius=1)
        pygame.draw.circle(cv, (24, 30, 46), (CW // 2 + 24, 6), 2)
        pygame.draw.rect(cv, (2, 3, 4), (SX - 2, SY - 2, SW + 4, SH + 4), border_radius=4)
        self.render_screen()
        a = clamp((self.now - self.trans) / .25, 0, 1)
        self.S.set_alpha(255)
        cv.blit(self.S, (SX, SY))
        # glass effects
        cv.blit(self.scan, (SX, SY))
        cv.blit(self.vig, (SX, SY))
        gx = int(self.mn[0] * 20)
        gl = pygame.Surface((SW, SH), pygame.SRCALPHA)
        pygame.draw.polygon(gl, (255, 255, 255, 9), [(60 + gx, 0), (110 + gx, 0), (30 + gx, SH), (-20 + gx, SH)])
        cv.blit(gl, (SX, SY))
        stat = self.static + (.08 if self.scr in APPS else .03)
        for _ in range(int(stat * 260)):
            v = random.randint(60, 200)
            cv.set_at((SX + random.randrange(SW), SY + random.randrange(SH)), (v, v, v, 255))
        if self.glitch > 0:
            for _ in range(4):
                y = random.randrange(SH - 16)
                hh = random.randint(3, 14)
                strip = cv.subsurface((SX, SY + y, SW, hh)).copy()
                cv.blit(strip, (SX + random.randint(-14, 14), SY + y))
                pygame.draw.line(cv, random.choice([(255, 0, 60, 120), (0, 255, 255, 110)]), (SX, SY + y), (SX + SW, SY + y))
        # caption bar (subtitles) and toasts
        pygame.draw.rect(cv, (5, 8, 10), (SX, CAPY, SW, CAPH))
        pygame.draw.rect(cv, LINE, (SX, CAPY, SW, CAPH), 1)
        ly = CAPY + 2
        if self.toast_t[1] > self.now:
            cv.blit(F1.render(fit(self.toast_t[0], F1, SW - 6), False, ACC), (SX + 3, ly))
            ly += 11
        if self.cap[2] > self.now:
            for ln in wrap(self.cap[0], F1, SW - 8)[:3 if ly == CAPY + 2 else 2]:
                cv.blit(F1.render(ln, True, self.cap[1]), (SX + 4, ly))
                ly += 10
        elif ly == CAPY + 2:
            cv.blit(F1.render('subtitles on', False, (40, 56, 56)), (SX + 4, ly))
        # nav bar
        blocked = bool(self.hack) or self.scr in ('title', 'brief', 'dead', 'solved', 'final')
        self.navb = [(pygame.Rect(36, 352, 44, 24), self.back), (pygame.Rect(86, 352, 44, 24), self.home),
                     (pygame.Rect(136, 352, 44, 24), lambda: self.set_mute(not self.muted))]
        nm = self.to_canvas(mp)
        for k, (r, fn) in enumerate(self.navb):
            hov = r.collidepoint(nm)
            en = not (blocked and k < 2)
            col = (WHITE if hov else TXT) if en else (50, 56, 60)
            if k == 0:
                pygame.draw.polygon(cv, col, [(52, 360), (64, 352), (64, 368)])
            elif k == 1:
                pygame.draw.circle(cv, col, (108, 360), 8, 2)
            else:
                pygame.draw.polygon(cv, col, [(150, 356), (155, 356), (161, 351), (161, 369), (155, 364), (150, 364)])
                if self.muted:
                    pygame.draw.line(cv, RED, (148, 352), (166, 368), 2)
                else:
                    pygame.draw.arc(cv, col, (160, 354, 8, 12), -1, 1, 1)
        if blocked:
            self.navb[0:2] = [(pygame.Rect(0, 0, 0, 0), lambda: None), (pygame.Rect(0, 0, 0, 0), lambda: None)]
        if self.case and self.scr in APPS and not (self.hack or self.scare or self.incoming):
            r = pygame.Rect(66, 337, 84, 12)
            pygame.draw.rect(cv, PANEL2, r, border_radius=2)
            cv.blit(F1.render('PUT DOWN', True, ACC), (78, 338))
            self.navb.append((r, self.return_drawer if self.scr == 'device' else lambda: self.enter_desk('desk')))
        if self.guide and self.difficulty!='Experienced' and self.case and self.scr in APPS and not (self.hack or self.scare or self.incoming):
            self.draw_phone_guide(cv)
        scaled = pygame.transform.smoothscale(pygame.transform.scale(cv, (CW * 3, CH * 3)), size)
        shd = pygame.transform.smoothscale(self.shadow_src, (size[0] + 24, size[1] + 24))
        self.win.blit(shd, (self.ox - 6, self.oy + 6))
        self.win.blit(scaled, (self.ox, self.oy))
        self.draw_corner_pip()
        pygame.display.flip()

    def run(self):
        if self.snd_ok:
            self.set_mute(False)
        self.render()
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, .05)
            if not self.suspended:self.now += dt
            for e in pygame.event.get():
                self.process_event(e)
            if self.suspended:
                continue
            self.update(dt)
            if self.mobile and self.now-self.last_autosave>=5:
                self.save_progress();self.last_autosave=self.now
            self.render()
        self.save_progress()
        self.save_notebook()
        try:
            if self.tts and self.tts.poll() is None:self.tts.terminate()
        except Exception:pass
        pygame.quit()


def main():
    Game().run()


if __name__ == '__main__':
    main()
