"""Create deterministic geometry exclusively for pipeline tests, never production output."""
import json
from pathlib import Path

def main(out: Path):
    out.write_text(json.dumps({
        'crs':'EPSG:6677','center_projected_m':[-2302.318,-36106.717],
        'buildings':[{'id':'TEST_FIXTURE_BUILDING_001','height_m':12.5,'height_source':'test fixture only',
            'source_file':'tests/fixture (synthetic; not survey data)',
            'footprints':[[[-10,-10],[10,-10],[10,5],[0,10],[-10,5],[-10,-10]]]}]
    },indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':
    import sys
    main(Path(sys.argv[1]))
