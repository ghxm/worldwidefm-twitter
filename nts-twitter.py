import argparse
import requests
import tweepy
import twitter_auth
import sqlite3
import re
import nts


def add_host_twitter(show_name):

    for name, user in nts.hosts.items():
        show_name = re.sub(f'(?:[\s^])({name})([?:\s$])', f'\g<1> (@{user})', show_name, flags=re.IGNORECASE|re.MULTILINE)

    return show_name

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("-n", "--numshows", help="Number of shows to check", default=25,
                    type=int)
    parser.add_argument("-t", "--text", help="Tweet text. Use {tw_name} and {url} to include upload name and url",
                        default = "{tw_name} ({date}, {location}) was uploaded to nts.live. Give it a listen for some {genres}. {url}",
                    type=str)
    parser.add_argument("-d", "--dry", help="Dry run (don't tweet)", action="store_true", default=False)
    args = parser.parse_args()

    offset = 0

    n_shows = 0

    client = tweepy.Client(bearer_token=twitter_auth.bearer_token, consumer_key=twitter_auth.consumer_key, consumer_secret=twitter_auth.consumer_secret,
                        access_token=twitter_auth.access_token, access_token_secret=twitter_auth.access_token_secret, wait_on_rate_limit=True)

    con = sqlite3.connect('nts.sqlite3', isolation_level=None)
    cur = con.cursor()

    while n_shows <= args.numshows:

        if n_shows >= args.numshows:
            break

        print('Fetching shows')

        url = f'https://www.nts.live/api/v2/search/episodes?offset={offset}&limit=12'

        feed = requests.get(url)

        feed_dict = feed.json()

        uploads = [{'name': r.get('title'), 'tw_name': add_host_twitter(r.get('title')), 'slug': r.get('article', {}).get('path'), 'url': 'https://www.nts.live' + r.get('article').get('path'), 'date': r.get('local_date'), 'location': r.get('location'), 'genres': [g['name'] for g in r.get('genres')]}  for r in feed_dict['results']]

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

            cur.execute('INSERT INTO episodes(name, slug, location, date, genres, posted) values (?, ?, ?, ?, ?, ?)',
                        (u['name'], u['slug'], u['location'], u['date'], str(u['genres']), e_posted))

            n_shows = n_shows + 1

        offset = offset + len(uploads)

    con.close()




if __name__ == "__main__":
    main()
