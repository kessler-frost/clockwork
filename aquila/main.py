# You don't always need an "agent" to execute a task, sometimes a normal function definition would do
# and allow for a more deterministic way of achieving a result - "agents" aka intelligence backends + task executors tend
# to not __always__ be deterministic and more dependent on things like what model - with configuration - you are using, how much
# context has been given, memory, etc. So putting a dial/knob on the level of intelligence required for an intelligent task should be
# adjustable. And in order for building things deterministically we need to start small -- with tasks which are not "intelligent"
# and then increase their complexity by combining them with other "dumb" tasks and slowly inject intelligence into them.

# ------ Conceptually, essentially how functional programming works -------

# Another feature/mechanism I want to have is essentially converting your "prompt" or your "discussion" (including "context")
# into a declarative and deterministic function that is converted into a non-human-readable binary, that is reusable
# in a completely different context BUT in a similar manner.

# The objective is to build a large assortment of tasks as functions. For example, a function ``
