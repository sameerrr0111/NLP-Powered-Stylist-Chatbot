% Western Family Relationships

% 1. Basic Parents
parent(X,Y) :- father(X,Y).
parent(X,Y) :- mother(X,Y).

% 2. REMOVED AUTOMATIC GENDER RULES 
% (We now save male/female explicitly in the python script)

% 3. Standard Rules
child(X,Y) :- parent(Y,X).

% Son: Must be male and a child
son(X,Y) :- male(X), parent(Y,X).

% Daughter: Must be female and a child
daughter(X,Y) :- female(X), parent(Y,X).

% Siblings
sibling(X,Y) :- parent(Z,X), parent(Z,Y), X \= Y.

brother(X,Y) :- male(X), sibling(X,Y).
sister(X,Y) :- female(X), sibling(X,Y).

% Grandparents
grandfather(X,Y) :- male(X), parent(X,Z), parent(Z,Y).
grandmother(X,Y) :- female(X), parent(X,Z), parent(Z,Y).
grandchild(X,Y) :- parent(Y,Z), parent(Z,X).
grandson(X,Y) :- male(X), grandchild(X,Y).
granddaughter(X,Y) :- female(X), grandchild(X,Y).

% Uncles/Aunts (Western)
p_uncle(X,Y) :- male(X), parent(Z,Y), brother(X,Z).
p_aunt(X,Y) :- female(X), parent(Z,Y), sister(X,Z).

% Cousins
cousin(X,Y) :- parent(Z,X), parent(W,Y), sibling(Z,W), X \= Y.

% --- EASTERN RELATIONSHIPS ---

% Abu/Ami
abu(X,Y) :- father(X,Y).
ami(X,Y) :- mother(X,Y).

% Taya (Father's elder brother) - Requires DOB logic or manual fact
taya(X,Y) :- male(X), father(Z,Y), brother(X,Z).

% Chacha (Father's brother - simplified)
chacha(X,Y) :- male(X), father(Z,Y), brother(X,Z).

% Mama (Mother's brother)
mama(X,Y) :- male(X), mother(Z,Y), brother(X,Z).

% Khala (Mother's sister)
khala(X,Y) :- female(X), mother(Z,Y), sister(X,Z).

% Dada/Dadi
dada(X,Y) :- father(Z,Y), father(X,Z).
dadi(X,Y) :- father(Z,Y), mother(X,Z).

% Nana/Nani
nana(X,Y) :- mother(Z,Y), father(X,Z).
nani(X,Y) :- mother(Z,Y), mother(X,Z).

% Beta/Beti
beta(X,Y) :- son(X,Y).
beti(X,Y) :- daughter(X,Y).

% Bhai/Behn
bhai(X,Y) :- brother(X,Y).
behn(X,Y) :- sister(X,Y).