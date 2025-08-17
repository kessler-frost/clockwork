# You don't always need an "agent" to execute a task, sometimes a normal function definition would do
# and allow for a more deterministic way of achieving a result - "agents" aka intelligence backends + task executors tend
# to not __always__ be deterministic and more dependent on things like what model - with configuration - you are using, how much
# context has been given, memory, etc. So putting a dial/knob on the level of intelligence required for an intelligent task should be
# adjustable. And in order for building things deterministically we need to start small -- with tasks which are not "intelligent"
# and then increase their complexity by combining them with other "dumb" tasks and slowly inject intelligence into them.

# ------ Conceptually, essentially how functional programming works when it comes to building intelligent task framework -------

# Another feature/mechanism I want to have is essentially converting your "prompt" or your "discussion" (including "context")
# into a declarative and deterministic function that is converted into a non-human-readable binary maybe, that is reusable
# in a completely different context BUT in a similar manner.

# The objective is to build a large assortment of tasks as functions that developers can just use to 
# simplify building bigger things - reducing friction, if not completely eliminating it, for technical details
# like a language, framework, etc., but giving them that in a package that they are comfortable with like say a typescript sdk.

# I want to build a factory of lego blocks.

# For example, (** = <sensible but variable number of inputs everytime>)
# level 1 intelligent task function is `eat_food(**)`, 
# level 2 is `eat_food_to_grow(**)`,
# level 3 is `eat_food_to_grow_and_kill_monster(**)`

# An adjacent function for that would be
# `eat_food_to_grow_and_pick_up_a_car(**)`


# "Agents" are just a medium of task resolution and not always the right answer

# Natural language is not deterministic and tribal knowledge is not in the codebase

# For example, an intelligent "compiler" can be built because it's simple to compile one thing into another locally as it
# doesn't require the model to be too smart

