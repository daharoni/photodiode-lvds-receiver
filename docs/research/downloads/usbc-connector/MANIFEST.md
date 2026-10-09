# MANIFEST: docs/research/downloads/usbc-connector/

Retrieved 2026-10-09. All files are untrusted raw downloads (CLAUDE.md). Text was extracted with `pdftotext` and parsed with `python3 -I`. Page numbers quoted in `../../usbc-connector-and-cable.md` are printed page numbers (spec) or PDF pages (datasheets).

| File | Source URL | SHA-256 | Notes |
|---|---|---|---|
| usb-typec-spec.html | https://www.usb.org/document-library/usb-type-cr-cable-and-connector-specification-release-23 | 12bce9334ff3d8427440866b8a64d5ace0528527b1446fd86c3100aee0025fec | usb.org document-library page; its link points to the Release 2.5 zip below |
| typec-r2.5.pdf | extracted from https://usb.org/sites/default/files/USB%20Type-C%202.5%20Release%20202603.zip (member "USB Type-C Spec R2.5 - March 2026.pdf") | 6636cd61387a2f78b0fa96c8ea86ccc0f39ec59f98821cdb57b206d31445a328 | USB Type-C Cable and Connector Specification Release 2.5, March 2026. The zip itself (29,756,254 bytes, SHA-256 603c2cb0ea356d367fea61f8747a21981f0da9abae4d8ec15556e0063edb81b5) was deleted after extraction to save space; the other zip members (ECN PDFs, R2.4 comparison, adopters agreement) were not kept or read |
| wurth-632723300011.pdf | https://www.we-online.com/components/products/datasheet/632723300011.pdf | 3c504f51cf0f241b3d81d1c6b022029473e1e5e5a414e66eb0f5ad66182bfb05 | Wuerth WR-COM USB 3.1 Horizontal Receptacle THR/SMT, 24 pins, drawing revision 003.000, 2025-09-04, 9 pages |
| gct-usb4115.pdf | https://gct.co/files/drawings/usb4115.pdf | 8e3448f72b96e77b0952160bfa76d54c034a7c7ce783411cfc70492e8d1b90dc | GCT USB4115 USB3.2 Gen2 Type C receptacle, vertical SMT, H=9.30 mm, revision B (PCN B8 17/12/25), 3 pages |
| gct-usb4110.pdf | https://gct.co/files/drawings/usb4110.pdf | b083cd7825c1d58d590e9b0ec6e8533ec43711b385d448d7b7a0fd25bd7f4d71 | GCT USB4110: USB 2.0 16-contact receptacle (evidence it is NOT 24-pin), revision B (PCN B4 22/05/24), 2 pages |
| gct-usb4085.pdf | https://gct.co/files/drawings/usb4085.pdf | 39afb82c5104579e8c2db4f4e758825c48cab1c4b06d4c61c62056470ff09e9e | GCT USB4085: USB 2.0 16-contact DIP receptacle (evidence it is NOT 24-pin), revision B (PCN B 28/02/23), 3 pages |
| ti-tpdxe05u06.pdf | https://www.ti.com/lit/ds/symlink/tpd4e05u06.pdf (the tpd6e05u06.pdf URL returns the identical file) | c167cf1e72a5473a4d2c59b6a3c0251498701da05b7785919b9ceaae3b3e02c6 | TI TPD1E05U06 / TPD4E05U06 / TPD6E05U06, SLVSBO7O, Aug 2024, 39 pages |
| ti-esd122.pdf | https://www.ti.com/lit/ds/symlink/esd122.pdf | 16ba54c64476aa5abbadc84ce72e60cee6baf710c958be0aad90cf363393f3ab | TI ESD122, SLVSDP5A, Aug 2018, 27 pages |
| nexperia-pusb3fr4.pdf | https://assets.nexperia.com/documents/data-sheet/PUSB3FR4.pdf | 9761c8e9b72727be75b42c4a213ad65a29d5f975cce554293ca2b8be4597c7f4 | Nexperia PUSB3FR4, 12 July 2018, 15 pages |

Attempted and not obtained: Amphenol 12401610E4#2A / 12401548E4#2A drawings (cdn.amphenol-cs.com returned HTTP 403), Molex 2171790001 and 1054500101 datasheets (molex.com: no connection), Wuerth 632723300112 (we-online.com URL returned 404), Nexperia PESD5V0X4UF (URL returned a 1.9 kB HTML stub), ST USBLC6-4 / USBLC6-2 (st.com: no connection).
