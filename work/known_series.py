rows = [l.rstrip('\n').split('\t') for l in open('crawl_games.tsv')]
print(','.join(sorted({r[1] for r in rows if len(r) > 1}, key=int)[-60:]))
