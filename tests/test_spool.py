from pathlib import Path
from unittest.mock import Mock
from manhwa import spool

def test_prepared_chapter_reused_after_failed_delivery(monkeypatch,tmp_path):
    monkeypatch.setenv('MANHWA_SPOOL',str(tmp_path))
    def build(source,url,folder):
        pdf=folder/'part-001.pdf';pdf.write_bytes(b'pdf');return [pdf],{'parts':1}
    builder=Mock(side_effect=build)
    monkeypatch.setattr(spool,'build_chapter',builder)
    job={'_id':'job','chapter_url':'chapter'}
    with spool.prepared(None,job) as (_,value):assert value[0][0].read_bytes()==b'pdf'
    with spool.prepared(None,job) as (_,value):assert value[1]['parts']==1
    assert builder.call_count==1
    spool.clean(job)
    assert not (tmp_path/'job').exists()
