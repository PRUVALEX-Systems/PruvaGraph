import json
from pathlib import Path
from collections import Counter

lines = Path('pruvagraph-out/benchmark_results.jsonl').read_text(encoding='utf-8').strip().split('\n')
summary = json.loads(lines[0])
questions = [json.loads(l) for l in lines[1:]]

tier_counts = Counter(q['method_used'] for q in questions)
total = len(questions)

print('=== TIER DISTRIBUTION ===')
for tier, count in sorted(tier_counts.items(), key=lambda x: -x[1]):
    print(f'  {tier:<30} {count:>3}  ({count/total*100:.1f}%)')

print()
print('=== tier_unknown SAMPLE (first 6) ===')
unknowns = [q for q in questions if q['method_used'] == 'tier_unknown']
for q in unknowns[:6]:
    preview = (q['answer_preview'] or '')[:100].replace('\n',' ')
    qtext = q['question'][:60]
    print(f'  Q: {qtext}')
    print(f'  A: {preview}')
    print()

print('=== SAVINGS STATS BY TIER ===')
for tier in tier_counts:
    qs = [q for q in questions if q['method_used'] == tier]
    avg_sav = sum(q['savings_pct'] for q in qs) / len(qs)
    print(f'  {tier:<30} avg_savings={avg_sav:.1f}%')
