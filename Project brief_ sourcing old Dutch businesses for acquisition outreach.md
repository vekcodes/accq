# **Project brief: sourcing old Dutch businesses for acquisition outreach**

GenFlows, 7 October 2026\. Author: Wouter Harink. Status: draft for review.

## **What we are trying to achieve**

We want to build a system that finds old, owner-run small businesses in the Netherlands, in a market of our choosing, and prepares outreach to the owners asking whether they would sell. The system should run per market (for example installation companies in Overijssel) from one command, cost almost nothing in data, and produce a ranked shortlist of 50 companies with a one-page dossier per company and draft letters, ready for a person to approve.  
The underlying idea is not new. Buyers of small businesses have for years looked for companies founded 30 or more years ago, still run by the founder, with no successor in sight, because those owners are the most likely to sell and often on favourable terms. What is new is that an AI model can do the list building, reading and judging that used to take weeks of manual work.

## **Where the idea comes from**

The trigger was this Instagram reel: [https\://www\.instagram.com/reel/DeHxLmCNNv9/](https://www.instagram.com/reel/DeHxLmCNNv9/?stkn=cXEzeDFzZ284M2Z1). The creator shows a US version of the pipeline built with Claude:

> 1. Download the SBA Paycheck Protection Program loan file and filter it to one industry, in his example plumbing companies in Texas.  
> 2. Look up each company's state registration date and keep the ones registered at least 30 years ago.  
> 3. Pull the current headcount from Department of Labor Form 5500 filings.  
> 4. Let a small model read every Google review per company and judge whether the owner still works in the business and whether a successor or new hires are mentioned.  
> 5. Email or mail the top 50 owners asking them to sell.

A commercial product doing roughly the same thing is [bizscout.com](https://www.bizscout.com/).

## **Why the Dutch version is different**

The Netherlands has no equivalent of the PPP file, and company headcount is not published the way Form 5500 publishes it. But the same signals exist in other places, and some are easier to get here:

> * Founding dates come from the KVK, from the company website ("sinds 1978", "familiebedrijf") and from the Wayback Machine's first capture of the domain.  
> * Size comes from the NOW and TVL corona support registers (free public lists of companies and amounts), LinkedIn employee counts, team pages and job postings.  
> * Owner age and succession come from LinkedIn career start years, the "over ons" page, local press (jubileum and overname stories), and the way owners reply to reviews.  
> * Reviews come from Google Maps, Werkspot, Klantenvertellen and Trustpilot.

The one thing the paid KVK extract gives that free sources do not is the birth date of a BV's directors. We would buy that only for the final 30 to 50 companies, at roughly 2.75 euro each, if at all.

## **How the system works**

The design is free-first. Paid data providers (KVK Dataservice, Company.info, Ad Hoc Data and similar) all resell the same fields per record, and that per-record cost is what we want to avoid. Compute is cheap, so the system reads everything for every company and filters at the end.

> 1. **Build the universe.** Union of three free sources, deduplicated on name and place: Clay's company search (Netherlands, trade keywords, 5 to 50 employees), Google Places searched per municipality (free monthly credit covers about 6,000 searches), and the NOW/TVL registers. A company present in two of the three is real, active and non-trivial.  
> 2. **Match the legal entity.** KVK number, legal form and owner name via the KVK search API, which costs cents per call.  
> 3. **Enrich per company.** Founding year, headcount, reviews, press and website signals. Every fetch is cached so no source is hit twice for the same company.  
> 4. **Classify succession.** A small Claude model reads all reviews, the about page and any press hit and returns: owner still active, successor named, new hires, recent ownership change, plus a one-line rationale. It ships with a labelled test set of Dutch review threads so prompt changes can be measured.  
> 5. **Score and rank.** Two hard filters (founded in or before 1996, 5 to 50 employees) and weighted signals: owner 60 or older, owner visibly operating, no successor found, NOW received, healthy review profile, website not updated in years. A named successor or recent ownership change counts heavily against.  
> 6. **Human check.** A person reads the top 50 dossiers and approves the batch. Nothing is sent automatically.  
> 7. **Outreach drafts.** Letters first, because this audience reads post and there are no legal restrictions on it. Email and phone depend on legal form: a BV can be emailed and called with an opt-out, but Dutch law treats eenmanszaken and VOFs as natural persons, so they need consent for email (Telecommunicatiewet article 11.7) and opt-in for calls.

## **First market and what comes after**

First market: installation companies (SBI 4322, loodgieters and cv-installateurs) in Overijssel. It is a fragmented trade with many founders from the 1970s to 1990s, it is review-heavy, and it is local to us. Market configs are small files, so the next markets are a copy-paste: electricians, painters, garages, veterinary practices, print shops, metalworking, road haulage, bookkeeping firms.

## **Technical shape**

A Claude Code project: a config file per market, numbered pipeline scripts, a DuckDB database per market run, and two skills (succession classifier and website signals) whose prompts are evaluated separately. Expected cost per market run: under 50 euro in model tokens, plus the optional 100 to 140 euro in KVK extracts.

## **Out of scope for the first version**

Valuation, financing, CRM integration, automatic sending, and anything that requires a KVK data subscription.

## **Data handling**

We store business contact details and derived signals only. No LinkedIn profile dumps, no birth dates outside the optional extract step, a suppression list per market, and the AVG legal basis written into the project instructions so every generated message respects it.

## **Open questions**

> * Is Clay plus Google Places plus NOW/TVL enough to catch old-school companies with no web presence, or do we need a fourth source such as industry association member lists?  
> * How reliable is the website and Wayback approach to founding year, and how do we handle BVs that were an eenmanszaak before their KVK date?  
> * Are the scoring weights right for Dutch trades?  
> * Who owns the labelled test set for the classifier?  
> * Do we build this as an internal tool only, or productise it later?