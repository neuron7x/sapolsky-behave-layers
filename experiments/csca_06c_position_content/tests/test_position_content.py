from experiments.csca_06c_position_content.run import POSITIONS,rotation_mapping,metrics,classify

def test_rotation_moves_each_content_through_every_position():
 for content in POSITIONS:
  seen={p for r in range(4) for p,c in rotation_mapping(r).items() if c==content}
  assert seen==set(POSITIONS)

def test_position_tracking_synthetic_classifies_locality():
 rows=[]
 for _ in range(4):rows.append({'fully_resolved':True,'position_tracking':1.0,'content_tracking':.25,'baseline_top_position':'A_RECENT'})
 m=metrics(rows);d=classify({'pooled':m,'PROSE':m,'CODE':m})
 assert d['position_pass'] is True and d['content_pass'] is False

def test_content_tracking_synthetic_classifies_content():
 rows=[]
 for _ in range(4):rows.append({'fully_resolved':True,'position_tracking':.25,'content_tracking':1.0,'baseline_top_position':'A_RECENT'})
 m=metrics(rows);d=classify({'pooled':m,'PROSE':m,'CODE':m})
 assert d['content_pass'] is True and d['position_pass'] is False
