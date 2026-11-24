"""Negative controls for frozen integration admission; no mutable trust root."""
from __future__ import annotations

import copy
import io
import json
import unittest
import zipfile

from scripts import cneh_exp05_integration as g


class TestIntegrationAdmission(unittest.TestCase):
    def archive(self, value, extra=False, corrupt=False):
        data=g.canonical(value)
        manifest=("0"*64 if corrupt else g.sha(data))+"  report.json\n"
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,"w") as z:
            z.writestr("report.json",data)
            z.writestr("SHA256SUMS",manifest)
            if extra:
                z.writestr("extra.json",b"{}")
        return buf.getvalue()

    def test_archive_negative_only(self):
        value={"experiment":"CNEH-TEST","scientific_promotion_authorized":False}
        raw=self.archive(value)
        reports,hashes=g.read_archive(raw,g.sha(raw),("report.json",))
        self.assertEqual(reports["report.json"],value)
        self.assertEqual(hashes["report.json"],g.sha(g.canonical(value)))

    def test_archive_outer_identity(self):
        raw=self.archive({"scientific_promotion_authorized":False})
        with self.assertRaisesRegex(ValueError,"external archive"):
            g.read_archive(raw,"0"*64,("report.json",))

    def test_archive_inner_manifest(self):
        raw=self.archive({"scientific_promotion_authorized":False},corrupt=True)
        with self.assertRaisesRegex(ValueError,"inner manifest"):
            g.read_archive(raw,g.sha(raw),("report.json",))

    def test_archive_roster(self):
        raw=self.archive({"scientific_promotion_authorized":False},extra=True)
        with self.assertRaisesRegex(ValueError,"ZIP member roster"):
            g.read_archive(raw,g.sha(raw),("report.json",))

    def test_rehashed_promotion_mutation(self):
        for value in (True,None,0,"false"):
            raw=self.archive({"scientific_promotion_authorized":value})
            with self.assertRaises(ValueError):
                g.read_archive(raw,g.sha(raw),("report.json",))

    def test_original_failure_cannot_be_relabelled(self):
        head,run,status=g.origin("x")
        meta={"id":run,"head_sha":head,"status":"completed","conclusion":status,
              "repository":{"full_name":g.REPO}}
        g.authenticate_run(meta,head,run,status)
        bad={**meta,"conclusion":"success"}
        with self.assertRaisesRegex(ValueError,"conclusion mismatch"):
            g.authenticate_run(bad,head,run,status)

    def test_expired_or_foreign_artifact(self):
        _,suffix,aid,digest,_=g.ARCHIVES[0]
        head,run,_=g.origin(suffix)
        meta={"id":aid,"digest":"sha256:"+digest,"expired":False,
              "workflow_run":{"id":run,"head_sha":head}}
        g.authenticate_artifact(meta,aid,digest,head,run)
        for mutation in ({"expired":True},{"digest":"sha256:"+"0"*64},
                         {"workflow_run":{"id":run+1,"head_sha":head}}):
            with self.assertRaises(ValueError):
                g.authenticate_artifact({**meta,**mutation},aid,digest,head,run)

    def test_workflow_body_preserved(self):
        raw=b"name: Frozen\non:\n  pull_request:\n    paths: ['x']\n  workflow_dispatch: {}\njobs:\n  work:\n    timeout-minutes: 5\n"
        self.assertEqual(g.archived_workflow(raw),
                         b"name: Frozen\non:\n  workflow_dispatch: {}\njobs:\n  work:\n    timeout-minutes: 5\n")

    def test_frozen_roster(self):
        self.assertEqual([x[0] for x in g.LINEAGES],[56,57,58,61,62,63,64,65,66,67,68,69,70,71])
        self.assertEqual([x[0] for x in g.LINEAGES if x[4]=="failure"],[56,63,67,70])
        self.assertEqual(len({x[2] for x in g.ARCHIVES}),20)


if __name__=="__main__":
    unittest.main()
