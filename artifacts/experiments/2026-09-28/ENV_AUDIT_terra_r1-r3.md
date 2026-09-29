# Environment audit — Terra r1–r3 (90 cells)

Manual, per cell, following the Shopping report's rule: a cell is excluded only when a
403 / Access Denied / CAPTCHA / Cloudflare / DNS failure / sustained timeout / unusable page
stopped evidence the persona actually asked for from being reached. Blocks on agent-built URLs,
on sources the persona never asked for, or ones the agent recovered from, are kept.

Candidates were found with `work/audit_evidence.py` plus a scan for Playwright navigation
failures with no later clean load from the same domain; every candidate was then read.

**KEEP 89 / EXCLUDE_RERUN 1.** Google served no bot wall in any of the 90 cells (743 successful searches).

| rep | task | persona | score | decision | note |
|---|---|---|---:|---|---|
| r1 | 5 | k12-teacher | 0.5 | **KEEP** | www.law.ubalt.edu certificate error on an agent-constructed hostname; the UBalt Visit page loaded and R2 was met. |
| r1 | 5 | none | 0.75 | **KEEP** | Same UBalt certificate error on an agent-constructed hostname; recovered, R2 met. |
| r1 | 1 | k12-teacher | 0.25 | **KEEP** | DNS failure on thepenpivot.com, a site the agent guessed; not a required source. |
| r1 | 3 | first-gen-applicant | 0.167 | **KEEP** | cdrdv2-public.intel.com triggered a file download, not a block. The persona never named Tom's Hardware and the agent chose other chips. |
| r1 | 6 | k12-teacher | 0.714 | **KEEP** | PubMed search page served a reCAPTCHA wall; the agent reached the peer-reviewed article through Google and PMC instead, so the requested evidence stayed reachable. |
| r1 | 6 | parent-helper | 0.714 | **KEEP** | PubMed search page served a reCAPTCHA wall; the agent reached the peer-reviewed article through Google and PMC instead, so the requested evidence stayed reachable. |
| r1 | 2 | none | 1.0 | **KEEP** | Cloudflare challenge on studylib.net, recovered elsewhere; score 1.0. |
| r2 | 5 | none | 1.0 | **KEEP** | Same UBalt certificate error; recovered, R2 met. |
| r2 | 4 | k12-teacher | 0.429 | **KEEP** | DNS failure on a search string typed into the URL bar; agent error, not environment. |
| r2 | 4 | parent-helper | 0.571 | **KEEP** | DNS failure on a search string typed into the URL bar; agent error, not environment. |
| r2 | 6 | faculty-advisor | 0.429 | **KEEP** | PubMed search page served a reCAPTCHA wall; the agent reached the peer-reviewed article through Google and PMC instead, so the requested evidence stayed reachable. |
| r2 | 6 | first-gen-applicant | 0.143 | **KEEP** | PubMed search page served a reCAPTCHA wall; the agent reached the peer-reviewed article through Google and PMC instead, so the requested evidence stayed reachable. |
| r2 | 6 | k12-teacher | 0.571 | **KEEP** | PubMed search page served a reCAPTCHA wall; the agent reached the peer-reviewed article through Google and PMC instead, so the requested evidence stayed reachable. |
| r2 | 6 | parent-helper | 0.857 | **KEEP** | PubMed search page served a reCAPTCHA wall; the agent reached the peer-reviewed article through Google and PMC instead, so the requested evidence stayed reachable. |
| r2 | 6 | none | 0.857 | **KEEP** | PubMed search page served a reCAPTCHA wall; the agent reached the peer-reviewed article through Google and PMC instead, so the requested evidence stayed reachable. |
| r3 | 5 | none | 0.25 | **KEEP** | ERR_CERT_COMMON_NAME_INVALID only on www.wcl.american.edu, a hostname the agent constructed; wcl.american.edu itself loaded cleanly 4 times. |
| r3 | 4 | parent-helper | 0.429 | **KEEP** | DNS failures only on agent-constructed URLs (a search string typed as a clinicaltrials.ucsf.edu hostname; silberman.hunter.cuny.edu); the real Silberman deadlines page was reached and R2 met. |
| r3 | 3 | first-gen-applicant | 0.5 | **EXCLUDE_RERUN** | The persona asked for the Intel Granite Rapids WS vs AMD Threadripper news. The Tom's Hardware article timed out twice (open_tab and click, 40 s each) and the fallback TechPowerUp article returned 403 Access Denied, so the environment stopped the requested evidence. |
| r3 | 6 | faculty-advisor | 0.286 | **KEEP** | Cloudflare challenge on one guilfordjournals.com article the agent chose for the cognitive-bias source; interchangeable sources exist and were reached in other cells. The other lost items are agent choices (Discogs instead of Wikipedia, weak thematic tie). |
| r3 | 2 | none | 1.0 | **KEEP** | Cloudflare challenge on slidesgo.com/education, recovered; score 1.0. |

All other cells: no environment signal on a requested source; KEEP.
