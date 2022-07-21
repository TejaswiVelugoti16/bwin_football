#pylint: disable=broad-except, logging-fstring-interpolation, line-too-long
import json
#import datetime
#import dataclasses
import queue
#import zoneinfo # will rely on tzdata if no system timezone data is installed.
#import time
import threading
from unicodedata import name
import re
import requests

import shared_tools

_SCRAPE_ID = 0  # this should match the scrape id for where the scrape is going
_BOOKIE = shared_tools.get_bookie_name(_SCRAPE_ID)
_TABLE_NAME = shared_tools.get_table_name(_SCRAPE_ID)
_SPORT = shared_tools.get_sport_name(_SCRAPE_ID)
_LOG = shared_tools.get_logger(_SCRAPE_ID)

_SUBMIT_QUEUE = queue.Queue()
_SUBMIT_QUEUE_CHECK_INTERVAL = 3


def get_events():

    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36',
    }

    try:
        response = requests.get(
            'https://sports.bwin.com/cds-api/bettingoffer/fixtures?x-bwin-accessid=NTZiMjk3OGMtNjU5Mi00NjA5LWI2MWItZmU4MDRhN2QxZmEz&lang=en&country=GB&userCountry=GB&fixtureTypes=Standard&state=Latest&offerMapping=Filtered&offerCategories=Gridable&fixtureCategories=Gridable,NonGridable,Other',
            headers=headers)
        str_json = response.content
        json_events = json.loads(str_json)
    except Exception:
        _LOG.exception(f'Response failure for events- response: {response.status_code}')
        return []
    successes = 0
    skipped = 0
    for i in json_events.get('fixtures'):
        try:
            event_name = i.get('name').get('value')
            if i.get('tournament'):
                tournament = i.get('tournament').get('name').get('value')
            else:
                tournament = ''
            team_names = []
            if len(i.get("participants")) == 2:
                team_names.append({'home':i.get('participants')[0].get('name').get('value'), 'short':i.get('participants')[0].get('name').get('value')})
                team_names.append({'away':i.get('participants')[1].get('name').get('value'), 'short':i.get('participants')[1].get('name').get('value')})
            else:
                for p in i.get("participants"):
                    if p.get('properties'):
                        if p.get('properties').get('type') == "HomeTeam":
                            team_names.append({"home":p.get('name').get('value'), "short":p.get('name').get('value')})
                        if p.get('properties').get('type') == "AwayTeam":
                            team_names.append({"away":p.get('name').get('value'), "short":p.get('name').get('value')})
            if i.get("games"):
                for g in i.get("games"):
                    for r in g.get('results'):
                        for t in team_names:
                            if re.sub('^[A-Z].*\. ','',str(r.get('name').get('value'))) in str(t.get('short')).split(' '):
                                t['odds'] = r.get("odds")
                            if r.get('name').get('value') == "Tie":
                                t['draw'] = r.get('odds')
            if team_names != []:
                for t in team_names:
                    if 'home' in t.keys():
                        if t.get('odds'):
                            team_1_odds = t.get('odds')
                        else:
                            team_1_odds = ""
                        team_1 = t.get('home')
                    if 'away' in t.keys():
                        if t.get('odds'):
                            team_2_odds = t.get('odds')
                        else:
                            team_2_odds = ""
                        team_2 = t.get('away')
                    if t.get('draw'):
                        draw = t['draw']
                    elif 'draw' not in t.keys():
                        draw = ''
                submit = {
                        'bookie': _BOOKIE,
                        'market': 'Match Result',
                        'tournament': tournament,
                        'url': 'https://sports.bwin.com/en/sports/events/'+re.sub('\s+','-',re.sub('[^a-zA-Z0-9 \n]','',str(i.get('name').get('value')).lower()))+'-'+str(i.get('id')),
                        'event date': i.get('startDate').split('T')[0],
                        'event name': event_name,
                        'home team': team_1,
                        'away team': team_2,
                        'outcomes': [team_1, 'Draw', team_2],
                        'event start': i.get('cutOffDate').split('T')[1],
                        'event end': i.get('cutOffDate').split('T')[1],
                        'odds': [team_1_odds, draw, team_2_odds]
                    }
                _SUBMIT_QUEUE.put(submit)
                successes += 1

        except:
            _LOG.warning('Match failed.', exc_info=True)
    _LOG.info(f'FoodBall Match data collected: {successes} - skipped {skipped}')

def main():
    """Main entry point into scrape."""
    # start the submission queue
    kwargs = {
        'SUBMIT_QUEUE_CHECK_INTERVAL': _SUBMIT_QUEUE_CHECK_INTERVAL,
        'TABLE_NAME': _TABLE_NAME,
        'SUBMIT_TO_AWS': False,
    }
    threading.Thread(target=shared_tools.submit_thread,
                     args=(_BOOKIE, _SPORT, _SUBMIT_QUEUE),
                     kwargs=kwargs,
                     daemon=True).start()
    get_events()

if __name__ == '__main__':
    main()
