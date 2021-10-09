#include <fstream>
#include <iostream>
#include <vector>
#include <map>

using namespace std;

#define TOKENS                \
    TOKEN(ID, "Id")           \
    TOKEN(COLON, "Colon")     \
    TOKEN(ENDLINE, "EndLine") \
    TOKEN(ENDFILE, "EndFile")

enum Token {
#define TOKEN(id, display) id,
    TOKENS
#undef TOKEN
};

const string TokenName[] = {
#define TOKEN(id, display) display,
    TOKENS
#undef TOKEN
};

class Lexer {
   public:
    explicit Lexer(std::istream& is);
    explicit Lexer(std::istream* ps);

    // A lexer belongs to a parser and should not be copied or moved.

    Lexer(const Lexer&) = delete;
    Lexer& operator=(const Lexer&) = delete;

    Lexer(Lexer&&) = delete;
    Lexer& operator=(Lexer&&) = delete;

    ~Lexer() {
        if (owns_input) delete p_input;
    }

    Token token() const { return cur_token; }
    std::string text() const { return buffer; }

    void advance() { cur_token = get_token(); }

   private:
    std::istream* p_input;  // The source stream (a stream of characters).
    bool owns_input;        // True if we can delete p_input, false if we can't.
    bool _end = false;

    Token cur_token;
    std::string buffer;

    Token get_token();
};

Lexer::Lexer(std::istream& is) : p_input{&is}, owns_input{false} { advance(); }
Lexer::Lexer(std::istream* ps) : p_input{ps}, owns_input{true} { advance(); }

bool isAlpha(char c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z');
}
bool isNum(char c) { return c >= '0' && c <= '9'; }
bool isAlphaNum(char c) { return isAlpha(c) || isNum(c); }

Token Lexer::get_token() {
    if(_end) return Token::ENDFILE;

    std::istream& input = *p_input;
    buffer.clear();

    char c = input.get();
    while (c == ' ') c = input.get();
    if (isAlphaNum(c)) {
        buffer = c;
        c = input.get();
        while (isAlphaNum(c)) {
            buffer += c;
            c = input.get();
        }
        input.putback(c);
        return Token::ID;
    }
    if (c == ':') {
        return Token::COLON;
    }
    if (c == '\n') {
        return Token::ENDLINE;
    }
    if (c == -1) {
        _end = true;
        return Token::ENDLINE;
    }
    throw "Unexpected character";
}

class Parser {
   public:
    Parser();

    map<string, vector<string>> operator()(istream& s);
    map<string, vector<string>> targets;

   private:
    Lexer* lex;
    string consume(Token t) {
        auto actual = lex->token();
        if (t != actual) {
            cout << "Expected token of type " << TokenName[t] << " but got " << TokenName[actual] << endl;
            throw -1;
        }
        auto value = lex->text();
        lex->advance();
        return value;
    }

    // Change these return types to double when we add semantics.
    void buildDescriptionList();
    void buildDescriptionLine();
    vector<string> parseDeps();
};

Parser::Parser() {}
map<string, vector<string>> Parser::operator()(istream& stream) {
    lex = new Lexer(stream);
    buildDescriptionList();
    delete lex;
    return targets;
}

void Parser::buildDescriptionList() {
    Token t;
    while ((t = lex->token()) != Token::ENDFILE) {
        buildDescriptionLine();
    };
}

void Parser::buildDescriptionLine() {
    if(lex->token() == Token::ENDLINE) {
        lex->advance();
        return;
    }

    string id = consume(Token::ID);
    consume(Token::COLON);
    vector<string> deps = parseDeps();
    consume(Token::ENDLINE);

    targets[id] = deps;
}

vector<string> Parser::parseDeps() {
    Token t;
    vector<string> result;
    while ((t = lex->token()) != Token::ENDLINE) {
        result.push_back(consume(Token::ID));
    }
    return result;
}

int main() {
    ifstream build("build.txt");
    Parser p;
    map<string, vector<string>> targets = p(build);
    for(const auto& entry: targets) {
        cout << entry.first << endl;
    }
}