# EdStemBot: A Read-Only RAG Assistant for EdStem Discussion Boards

Author: Carl Kaziboni, University of Edinburgh. TeachAthon submission. (EdStemBot is now branded askEd.)

## Abstract

Understaffed Computer Systems courses struggle to keep up with EdStem discussion boards: the same questions (deadlines, FAQ-type clarifications, recurring conceptual sticking points) get asked repeatedly because earlier answers are buried in old threads and hard to find, and course organisers have no structured view of which concepts are genuinely causing difficulty until it shows up at the exam.

EdStemBot is a read-only support tool built around both problems. It watches a course's EdStem threads, matches each new question against course notes and past staff answers using retrieval-augmented generation (RAG), and surfaces a dashboard that TAs can use day-to-day to spot and resolve repeated questions, and that course organisers can use at mid-term review to see which topics are the real pain points and where the course material or delivery could be improved.

A companion Chrome extension gives students a grounded AI answer preview directly on a thread, cutting down the number of "already answered" questions TAs have to handle one by one. It never posts, edits or alters EdStem content, and all AI output is clearly labelled as a preview, keeping staff in control.

## 1. Introduction and Problem Statement

On busy EdStem boards for Computer Systems modules, the same handful of questions resurface constantly: deadlines, clarifications already answered days earlier, and recurring conceptual sticking points (virtual memory, concurrency, assembly syntax). In a well-staffed course this repetition is manageable; in an understaffed one it quickly becomes the majority of TA workload.

The issue is not that answers don't exist, it's that they get lost in the forum: EdStem has no structured way to say "this exact question was answered three days ago", so TAs either re-answer from scratch or search old threads themselves.

A second, related gap sits at the course level. Organisers typically only learn which concepts students struggled with when exam or coursework results come in, too late to adjust that term's teaching. EdStem gives no aggregate view of which topics generate the most confusion over time; a mid-term check-in on "what is actually difficult this term" currently depends on staff noticing a pattern informally.

This gap sits between two example use cases in the brief: streamlining administrative and support processes, and automating feedback for students. EdStemBot targets both levels: giving stretched TA teams day-to-day visibility into repeated questions, and giving course organisers a mid-term evidence base for which concepts need more coverage, a different explanation, or a change next time.

## 2. Proposed Solution

### a) Process supported

EdStemBot watches a course's EdStem threads in real time via EdStem's WebSocket stream (read-only; it never posts, edits or deletes anything on EdStem). Each new question is matched against the course's own lecture notes and, crucially, against past staff-answered threads, then tagged with one or more of 15 Computer Systems topics.

This feeds a dashboard with two uses. Day-to-day, TAs use it to see at a glance which questions are recurring, including administrative ones like deadlines, rather than discovering the pattern thread by thread, so they can act on it once (pin an answer, clarify in a lecture) rather than re-answer it every time it resurfaces.

At mid-term, course organisers use the same topic distribution and trend data as a review tool: which topics generated the most questions, which spiked around a particular lecture or coursework, and which stayed in the low-confidence "needs review" queue, as evidence for what to revisit, re-explain, or restructure before the next cohort.

Separately, a Chrome extension adds a panel directly on the EdStem thread page: before a student posts a new question, they can request an AI answer preview grounded in the course notes and prior staff answers (with topic tags, a confidence score and cited sources), or a short multiple-choice quiz on the thread's topic for self-testing. This is aimed squarely at reducing the volume of near-duplicate questions reaching TAs in the first place.

### b) Technology (conceptual level)

Course PDFs and staff-answered threads are chunked and embedded, then stored in a vector database for retrieval-augmented generation: each incoming question is matched against the most relevant chunks of real course material and prior answers before an LLM responds, so output is grounded and cites its sources rather than being invented.

A shared backend exposes this through two surfaces: a dashboard (read-only analytics, used by both TAs day-to-day and organisers at mid-term) and a small local API the Chrome extension calls. The system is LLM-provider agnostic (OpenAI, Gemini or Claude, swappable by configuration), so a department is not locked into one vendor, and it keeps improving as staff answer more threads, since those answers become searchable knowledge for next time rather than being lost once the thread scrolls away.

### c) Prototype

A working implementation (backend, dashboard and Chrome extension) is available at https://github.com/carlkaziboni/EdStemBot.

Figures in the submission show: the lecturer analytics dashboard overview for a live Computer Systems course; dashboard detail views (topic trends, ranked topics, recent activity feed, and the lecturer review queue with low-confidence flags, with student identifiers redacted); and the Chrome extension on a live EdStem thread showing a grounded answer preview and a multiple-choice quiz.

## 3. Implications and Ethical Considerations

### Wider fit

For understaffed courses, this tool could change TA workload: instead of each TA independently re-discovering which questions are repeating, the dashboard makes that pattern visible to the whole team immediately. At the course level, it gives organisers a mid-term, evidence-based view of difficult concepts, something that currently only emerges informally or after the exam, feeding into course improvement rather than just staff intuition.

It sits alongside EdStem rather than replacing staff: the AI answer is labelled as a preview, not an official answer, and the read-only design means staff retain full control of what gets posted.

### Benefits

Reduces the burden of repeated or duplicate questions on small TA teams, surfaces administrative FAQs so they can be pinned once, gives organisers a mid-term signal on genuinely difficult topics, and gives students a faster, cited first step without waiting for a stretched TA.

### Risks and mitigations

1. Hallucinated answers: mitigated by grounding every answer in retrieved course-note and staff-answer excerpts with a confidence score, discarding low-similarity matches, and labelling output as an unverified preview.
2. Over-reliance: students could treat the preview as authoritative and stop engaging with staff or peers; visible confidence scores and encouraging posting regardless help offset this.
3. Bias and fairness: classification quality depends on what material is ingested, so under-covered topics could get worse answers, and the same skew could distort the mid-term "difficult topics" picture organisers rely on; the "needs review" queue helps catch this, which matters more for understaffed courses with less capacity to check manually.
4. Privacy: question text is sent to a third-party LLM provider, requiring institutional sign-off; the system supports locally-run or specific providers to help meet requirements.
5. Transparency: students should be clearly told the extension exists, is optional, and is not run or endorsed by EdStem itself.

### Unintended consequences

Widespread use could shift question-asking behaviour (for example fewer peer-to-peer answers if the AI preview satisfies most queries), worth monitoring via the analytics the tool already produces.

## References

1. EdStem. API documentation. https://edstem.org.
2. Lewis, P. et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS, 2020.
3. Reimers, N. and Gurevych, I. Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks. EMNLP, 2019.
4. EdStemBot source code and documentation. https://github.com/carlkaziboni/EdStemBot.
