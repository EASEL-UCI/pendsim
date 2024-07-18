pendsim: A Pendulum-on-a-cart Simulator!
========================================

.. toctree::
   :maxdepth: 2
   
   Install <install>
   Tutorial <tutorial>
   Write Your Own Controller <customctl>
   Advanced Plotting <PlottingTutorial>
   Example: Linearization <Linearization>
   Example: PID Control <PID>
   Example: Swing-Up <SwingUp>
   Example: State Estimation <StateEstimation>
   Example: LQR <LQR>

pendsim is a package for exploring dynamics, control, and state estimation
techniques, in the context of every control theorist's favorite system: the 
inverted pendulum-on-a-cart problem!

.. note::
   For a summary of the package features, as well as how it can be used in an educational context, see the Journal of Open Source Education (JOSE) paper: https://doi.org/10.21105/jose.00168

.. image:: _static/diagram.png

It can serve as a companion to any control theory textbook that 
includes the classic pendulum problem, or as a utility for creating virtual labs, 
visualizations, programming assignments, and more! Or, you can use it for exploring 
or validating experimental techniques.

Citing
------

To cite pendsim please use the following:

Sutherland, M. L. and Copp, D. A. (2023). pendsim: Developing, Simulating, and Visualizing Feedback Controlled Inverted Pendulum Dynamics. Journal of Open Source Education, 6(61), 168, https://doi.org/10.21105/jose.00168

Audience
--------

I wrote `pendsim` to explore concepts relating to dynamical systems, control theory,
state estimation, and machine learning in a controls-related context. Therefore,
`pendsim` is written primarily for the student or educator. But, if you use it for
anything else, I would love to know!

Python
------

Python is a powerful programming language that enables high productivity. It has
a very developed package ecosystem, including sophisticated packages for scientific
and technical computing. To make the most out of this package, you will want to 
know how to write basic programs in Python.  Among the many guides to Python, we
recommend the `Python documentation <https://docs.python.org/3/>`_ or the UC Irvine
`ICS 31 Notes by Prof. Pattis. <https://www.ics.uci.edu/~pattis/ICS-31/index.html>`_


License
-------

.. include:: ../LICENSE
