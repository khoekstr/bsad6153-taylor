# Implementation Brief: AI Research Discovery

## 1. Workflow and Baseline

About twice a week, I decide what AI material to read or watch. I previously relied on YouTube, LinkedIn, and Google, but often couldn't tell whether something was credible, genuinely new, or clickbait. My Week 1 baseline showed searches taking 1–30 minutes, including 10 minutes choosing a YouTube video and 30 minutes exploring OpenAlex. Confidence in my selections was generally low.

I also realized I wanted more than AI news. I wanted to explore research, save my reflections, and connect ideas across different topics. My database began with 504 OpenAlex articles and now includes additional references, personal notes, AI assessments, and suggested connections. The next step is a website that makes this information easy to use.

## 2. Should This Use AI?

**A. No custom application:** I could continue using Google, ChatGPT, Excel, and Word. This avoids development costs but leaves my information scattered across different tools. Finding previous notes and maintaining context would remain time-consuming.

**B. Database without LLM chat:** A website with SQL searches and filters could organize articles, track reading, and retrieve my notes. This requires development and maintenance but no conversational API costs. It would handle retrieval well, although interpreting relationships across articles would remain largely manual.

**C. Database with LLM chat:** This is my preference. For example, SQL could find unread articles about AI in education, but I'd like to ask how my previous thoughts about AI tutors relate to new research on student motivation. An LLM could help make those connections.

The trade-offs are API costs, complexity, and potentially inaccurate interpretations. I don't need AI for storage or basic searches. **The question is whether conversational analysis adds enough value to justify it.** That's what I intend to test.

## 3. Value Hypothesis

My goal isn't necessarily to save time. I want to explore AI research more deeply while continuing to discover new interests, potentially leading to projects, collaboration, or a future career.

My initial target is using the application **twice weekly for three weeks**, documented in a simple usage log. However, usage alone doesn't demonstrate value.

In Milestone 4, I'll establish a baseline by asking an LLM five research questions without my database. In Milestone 5, I'll repeat them with database access, comparing accuracy, relevance, and use of my stored research and notes. My proposed target is **better answers on at least four of five questions**, without unsupported claims. If the chatbot doesn't consistently improve results, I'll reconsider whether it's worth the additional complexity.

## 4. Early Cost Estimate

I currently pay $20/month for ChatGPT Plus, which I've used with Astra to develop the workflow and initial assessments. Separate API spending is currently $0.

For the application, I expect approximately **$2/month in API costs, with a $5 hard cap**. I anticipate 10 new articles weekly and two chat sessions per week. OpenAlex, Supabase, GitHub Actions, and Render offer free tiers I plan to use.

An illustrative GPT-6.1 Terra calculation suggests approximately $0.37 monthly for 45 assessments and nine chat sessions, but actual usage and pricing need verification. I'll use prepaid API credits without automatic recharge and implement a spending check to stop paid calls before the $5 limit. AI features would pause, but existing research and notes would remain accessible.

## 5. Risks and Governance

My biggest concerns are poor usability, losing notes, and AI misrepresenting research. Current assessments are explicitly abstract-based, and their 1–5 ratings measure personal relevance, **not research credibility**. They help me choose what to read but shouldn't be presented as verified findings.

My notes and questions require authenticated access and recovery options. The AI may edit or delete notes only with my direction and must never access passwords or financial information, subscribe, or comment on my behalf.

Although initially for personal use, the website will be public. Visitors must not access private notes or mistake AI assessments for verified conclusions. Expanding to multiple users would require additional protections.

## 6. Implementation Scorecard v1

| Factor                            | Rating | Reasoning                                                                                 |
| --------------------------------- | ------ | ----------------------------------------------------------------------------------------- |
| 1. Real user and workflow         | Green  | I'm the initial user, addressing a problem I've experienced firsthand.                    |
| 2. Data access                    | Yellow | OpenAlex works well, but access to future sources like YouTube is uncertain.              |
| 3. Data understanding             | Yellow | I know the abstract and missing-data limitations; credibility remains unresolved.         |
| 4. Freshness and monitoring       | Yellow | `sync_runs` tracks updates, but incoming article usefulness isn't evaluated consistently. |
| 5. Grounding                      | Yellow | The database provides evidence, but chatbot grounding hasn't been tested.                 |
| 6. Bounded autonomy               | Yellow | Human and AI content are distinguished; agent permissions remain untested.                |
| 7. Evaluation                     | Yellow | Success criteria are defined, but comparisons haven't been completed.                     |
| 8. Measured value and cost        | Yellow | Costs appear low, but benefits and full costs haven't been measured.                      |
| 9. Adoption                       | Red    | Consistent use depends on an interface that hasn't been built.                            |
| 10. Governance and accountability | Red    | I'm accountable, but website privacy and note recovery aren't tested.                     |

### Plans for the Two Weakest Factors

**Adoption:** I'll use the website for my normal research, identify frustrations, make changes, and repeat. My usage goal will help determine whether it becomes part of my routine.

**Governance and accountability:** Before relying on the website, I'll test login protection, private-note access, saved-note persistence, and recovery of edited or deleted notes.

---

*AI Use Statement: All thoughts and assessments are my own. I used AI to organize my ideas, assist with cost estimates, and improve the writing. I reviewed and revised the draft to reflect my reasoning and conclusions.*
