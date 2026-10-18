import httpx
import pytest
from manhwa.telegram import Telegram, DeliveryUnknown, DeliveryRejected


def test_document_streams_with_separate_upload_timeout(monkeypatch,tmp_path):
    path=tmp_path/'chapter.pdf';path.write_bytes(b'pdf'*50000)
    bot=Telegram('test-token');progress=[];bot.progress=lambda n,total:progress.append((n,total))
    def post(url,*,content,headers,timeout):
        assert timeout.connect==20 and timeout.write==600
        chunks=list(content)
        assert max(map(len,chunks))<=65536
        assert sum(map(len,chunks))==int(headers['Content-Length'])
        assert b'pdfpdf' in b''.join(chunks)
        return httpx.Response(200,json={'ok':True,'result':{'message_id':1,'document':{'file_id':'file'}}})
    monkeypatch.setattr('manhwa.telegram.httpx.post',post)
    assert bot.document('channel',path,'caption','chapter.pdf')['message_id']==1
    assert progress[-1][0]==progress[-1][1]


@pytest.mark.parametrize('exception,expected',[(httpx.ConnectTimeout,DeliveryRejected),(httpx.WriteTimeout,DeliveryUnknown),(httpx.ReadTimeout,DeliveryUnknown)])
def test_upload_timeout_classification(monkeypatch,tmp_path,exception,expected):
    path=tmp_path/'chapter.pdf';path.write_bytes(b'pdf')
    def post(*args,**kwargs):raise exception('timeout')
    monkeypatch.setattr('manhwa.telegram.httpx.post',post)
    with pytest.raises(expected):Telegram('test-token').document('channel',path,'caption','chapter.pdf')
