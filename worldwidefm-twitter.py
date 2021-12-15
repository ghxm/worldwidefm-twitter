import argparse
import requests
import tweepy
import twitter_auth
import sqlite3
import re
import nts
import worldwidefm


def add_host_twitter(show_name):

    hosts = nts.hosts
    hosts.update(worldwidefm.hosts)

    for name, user in hosts.items():
        show_name = re.sub(fr'(?:\b|^)({name})(?:\b|$)', f'\g<1> (@{user})', show_name, count=1, flags=re.IGNORECASE|re.MULTILINE)

    return show_name

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("-n", "--numshows", help="Number of shows to check", default=25,
                    type=int)
    parser.add_argument("-t", "--text", help="Tweet text. Use {tw_name} and {url} to include upload name and url",
                        default = "{tw_name} ({date}) was uploaded to worldwidefm.net. Give it a listen for some {genres}.\n{url}",
                    type=str)
    parser.add_argument("-d", "--dry", help="Dry run (don't tweet)", action="store_true", default=False)
    args = parser.parse_args()

    args.text = args.text.replace('\\n', '\n')

    offset = 0

    n_shows = 0

    client = tweepy.Client(bearer_token=twitter_auth.bearer_token, consumer_key=twitter_auth.consumer_key, consumer_secret=twitter_auth.consumer_secret,
                        access_token=twitter_auth.access_token, access_token_secret=twitter_auth.access_token_secret, wait_on_rate_limit=True)

    con = sqlite3.connect('worldwidefm.sqlite3', isolation_level=None)
    cur = con.cursor()

    while n_shows <= args.numshows:

        if n_shows >= args.numshows:
            break

        print('Fetching shows')

        url = f'https://worldwidefm.net/cached_api'

        payload = {"operationName":"getEntries","variables":{"offset":offset,"limit":50,"section":"episode","player":["not",""]},"query":"query getEntries($section: [String], $offset: Int, $limit: Int, $player: [QueryArgument]) {\n  entries(\n    section: $section\n    limit: $limit\n    offset: $offset\n    player: $player\n    orderBy: \"broadcastDate DESC, postDate DESC\"\n  ) {\n    id\n    uri\n    title\n    postDate @formatDateTime(format: \"d.m.y\")\n    ...ScheduleDay\n    ...Offers\n    ...Editorial\n    ...Episode\n    __typename\n  }\n}\n\nfragment ScheduleDay on scheduleDay_scheduleDay_Entry {\n  scheduleDate @formatDateTime(format: \"yy-m-d\", timezone: \"Europe/London\")\n  scheduleContent {\n    id\n    __typename\n    ... on scheduleContent_scheduleDayItems_BlockType {\n      startTime @formatDateTime(format: \"GG:i\", timezone: \"Europe/London\")\n      endTime @formatDateTime(format: \"GG:i\", timezone: \"Europe/London\")\n      altTitle\n      episode {\n        title\n        uri\n        __typename\n      }\n      __typename\n    }\n  }\n  __typename\n}\n\nfragment Offers on offers_offers_Entry {\n  offerCode\n  offerDate\n  offerLink\n  offerState\n  offerText\n  offerType\n  postDate @formatDateTime(format: \"d.m.y\")\n  __typename\n}\n\nfragment Editorial on editorial_editorial_Entry {\n  id\n  title\n  description\n  thumbnail {\n    url @transform(width: 1200, height: 1200, immediately: true)\n    __typename\n  }\n  postDate @formatDateTime(format: \"d.m.y\")\n  __typename\n}\n\nfragment Episode on episode_episode_Entry {\n  id\n  title\n  description\n  thumbnail {\n    url @transform(width: 1200, height: 1200, immediately: true)\n    __typename\n  }\n  genreTags {\n    title\n    slug\n    __typename\n  }\n  broadcastDate @formatDateTime(format: \"d.m.y\")\n  episodeCollection {\n    id\n    title\n    uri\n    __typename\n  }\n  __typename\n}\n"}
        feed = requests.post(url, json=payload)

        feed_dict = feed.json()

        uploads = [{'name': r.get('title'), 'tw_name': add_host_twitter(r.get('title')), 'slug': r.get('uri'), 'url': 'https://www.worldwidefm.net/' + r.get('uri'), 'date': r.get('postDate'), 'location': r.get('location', ''), 'genres': [g['title'] for g in r.get('genreTags')]}  for r in feed_dict['data']['entries']]

        print(str(len(uploads)) +  ' found')

        for u in uploads:

            if n_shows >= args.numshows:
                break

            # check if alread posted

            posted_shows = [row for row in cur.execute('SELECT * FROM episodes WHERE slug = ? and posted=1', (u['slug'],))]

            if len(posted_shows)>0:
                posted = True
                n_shows = n_shows + 1
            else:
                posted = False
            if posted:
                continue

            if len(u['name']) == 0:
                u['name'] = "Some show"

            if len(u['location']) == 0:
                u['location'] = "the internet"

            if len(u['genres'])==0:
                u['genres'] = ['music']

            if len(u['date']) == 0:
                u['date'] = "at some point in time"


            text = args.text.format(name = u['name'], tw_name=u['tw_name'], url = u['url'], date = u['date'], location = u['location'], genres=' & '.join(filter(None, [', '.join(u['genres'][:-1])] + u['genres'][-1:])))

            try:

                if not args.dry:
                    tw_response = client.create_tweet (text=text)

                print(text + '\n\t' + ("Tweet posted"))
                e_posted=1

            except Exception as e:
                print(text + '\n\t' + ("Tweet not posted:\n" + str(e)))
                e_posted = 0

            if not args.dry:
                cur.execute('INSERT INTO episodes(name, slug, location, date, genres, posted) values (?, ?, ?, ?, ?, ?)',
                        (u['name'], u['slug'], u['location'], u['date'], str(u['genres']), e_posted))

            n_shows = n_shows + 1

        offset = offset + len(uploads)

    con.close()




if __name__ == "__main__":
    main()
