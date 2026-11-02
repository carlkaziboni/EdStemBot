# askEd approved FAQ

Status labels used below: Implemented (built and working in the prototype), Prototype limitation (works but with a known constraint), Idea (not built), Not evaluated (no measurement has been made), Unknown (not covered by these materials).

## What is askEd?

askEd is the new name for EdStemBot. It is a read-only assistant for EdStem discussion boards, built for Computer Systems courses. It has three parts, all Implemented: a lecturer analytics dashboard, a student Chrome extension, and this live audience Q&A page. It never posts to, edits, or deletes anything on EdStem.

## How does askEd work? (RAG)

Implemented. Course PDFs are split into 500-character chunks with 100 characters of overlap, turned into vectors with the all-MiniLM-L6-v2 embedding model, and stored in a ChromaDB vector database. When a question arrives, the most relevant chunks (up to 5, dropping any with cosine distance above 0.6) are retrieved and given to a language model, which answers using only that context and cites its sources. Staff-answered EdStem threads can also be indexed as extra knowledge with a separate script.

## Which AI models does askEd use?

Implemented. The language model is swappable by configuration: OpenAI (default gpt-4o-mini), Google Gemini (default gemini-1.5-flash) or Anthropic Claude (default claude-haiku-4-5). One interface hides the differences, so a department is not locked into one vendor.

## How does askEd handle hallucinations?

Implemented mitigations: answers are grounded in retrieved excerpts and cite their sources; matches that are not similar enough are discarded; if nothing relevant is found, askEd says it does not know instead of guessing; and output is labelled as an AI preview, not an official answer. Prototype limitation: the confidence score shown is the similarity of the best retrieved chunk. It is not a calibrated probability that the answer is correct. Not evaluated: the factual accuracy of answers has not been formally measured.

## Is it safe for privacy and security?

Implemented: EdStem access is read-only. Question text is sent to the configured third-party language model provider, so a real deployment needs institutional sign-off (Prototype limitation, and a risk named in the proposal). The Chrome extension talks only to a local server and protects it with a shared secret. In the public live deployment, only the audience and presenter pages are mounted; the lecturer dashboard and extension API are not exposed, the presenter pages need a secret key, the interactive API docs are disabled, and questions are rate limited. Audience participation is anonymous: no account or name is requested, a random ID is kept in the phone's browser, and submitted questions are stored in the deployment's database. Participants are asked not to enter personal details.

## How does askEd integrate with EdStem?

Implemented. It listens to a course's live thread events over EdStem's WebSocket stream and backfills recent questions through the REST API, using a personal EdStem API token and the course ID. It only reads. Each new question is classified into one or more of 15 Computer Systems topics and logged. Prototype limitation: it is not run or endorsed by EdStem, and it depends on EdStem's API and page structure, which can change.

## What is the student experience?

Implemented. The Chrome extension adds a collapsible panel to an EdStem thread page. Students can request an AI answer preview with topic tags, a match-confidence figure and cited sources, or take a short multiple-choice quiz on the thread's topic with instant feedback and explanations. Nothing is sent to the model until the student opens the panel. Prototype limitation: it runs against a local server, so it must be started by the operator, and the selectors that find the question text on EdStem's page may need adjusting if EdStem changes its markup.

## What does the lecturer dashboard show?

Implemented. Key numbers, question counts per topic, 7-day topic trends, an activity heatmap by day and hour, recent questions, and a "needs review" queue of low-confidence or unclassified questions. Intended uses are day-to-day spotting of repeated questions by TAs and a mid-term view for course organisers of which topics generate the most questions. Important: a question count shows interest or concern, not necessarily confusion. Prototype limitation: the local dashboard has no login, so it must not be exposed publicly.

## How can it be deployed, and does it scale?

Implemented: the app is a single FastAPI service using SQLite and ChromaDB, and it can run locally or on a host such as Render. This live demo runs in a public mode with a lighter embedding runtime (fastembed) suited to small servers. Prototype limitation: it runs as one instance, the rate limiting and response caches are held in memory, and it has not been load tested at scale. Unknown: costs at institutional scale are not covered by these materials.

## What is the educational impact?

Not evaluated. No learning gains, reduction in TA workload, or answer accuracy have been measured. The proposal describes expected benefits: fewer repeated questions for small TA teams, FAQs surfaced so they can be pinned once, a mid-term signal on difficult topics, and a faster cited first step for students. It also names risks: over-reliance on the AI preview, fewer peer-to-peer answers, bias if some topics are under-covered, and privacy of question text.

## What do the results on the screen in this talk mean?

The quiz results show the share of answers that were incorrect for each topic in a short mini quiz taken by people in this room. That is performance on a handful of questions, not a measure of understanding or of confidence. The sample is small and self-selected, so the results are illustrative only, not a formal measurement of learning. Questions asked are counted by topic and show what this room was curious about.

## What is planned or only an idea?

Idea, not built: streamed answers, quiz history and spaced repetition for missed questions, clickable citations that open the source PDF page, a follow-up question box in the extension, a hosted backend so a whole class can use the extension without running anything locally, and a self-reported confidence rating alongside questions in the live demo. Unknown: no timeline or pilot course is stated in these materials.

## What are the main limitations?

Prototype limitations: topics are a fixed list of 15 Computer Systems topics; answer quality depends on which material has been ingested and on how well text can be extracted from PDFs (scanned PDFs without a text layer will not index well); quiz questions are drafted by an AI from the notes and need human review before use; the extension is for Chrome; and the whole system is a prototype that has not been evaluated with students.

## Who made askEd and where is the code?

askEd was created by Carl Kaziboni at the University of Edinburgh as a TeachAthon submission. The source code and documentation are at https://github.com/carlkaziboni/EdStemBot.
