"""Render a PR plan without requiring git or a GitHub remote."""
from __future__ import annotations
import argparse, json
from datetime import date

def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument('--game-version', required=True); p.add_argument('--new', type=int, required=True); p.add_argument('--modified', type=int, required=True); p.add_argument('--removed', type=int, required=True); a=p.parse_args()
    branch=f"codex/wakfu-{a.game_version.replace('.', '-')}-{date.today():%Y%m%d}"
    changed=['Ceviri_Verileri/wakfu_tr_ceviri.json','automation/state.json',f'automation/snapshots/{a.game_version}.json','Raporlar/wakfu-update-report.json']
    body=(f"## WAKFU localization update\n\nGame version: `{a.game_version}`\n\n"
          f"- NEW: {a.new}\n- MODIFIED: {a.modified}\n- REMOVED: {a.removed}\n\n"
          "Automated candidates require human review. No Release is created by this PR.")
    print(json.dumps({'branch':branch,'commit':f'WAKFU localization update for {a.game_version}','changed_files':changed,'pr_title':f'WAKFU localization update: {a.game_version}','pr_body':body},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
