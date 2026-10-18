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


def test_lost_cache_after_partial_delivery_never_rebuilds_from_another_source(monkeypatch,tmp_path):
    import pytest
    monkeypatch.setenv('MANHWA_SPOOL',str(tmp_path))
    builder=Mock();monkeypatch.setattr(spool,'build_chapter',builder)
    with pytest.raises(RuntimeError,match='partial delivery'):
        with spool.prepared(None,{'_id':'partial','chapter_url':'chapter','sent_parts':[{'message_id':5}]}):
            pass
    builder.assert_not_called()
