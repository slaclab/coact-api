import Row from "react-bootstrap/Row";
import Col from "react-bootstrap/Col";
import Card from "react-bootstrap/Card";
import Button from 'react-bootstrap/Button';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faRocket  } from '@fortawesome/free-solid-svg-icons'

export default function LandingPage() {
  return (
    <div className="content" id="landingpage">
      <Row>
        <Col>
          <Card className="text-center">
            <Card.Body>
              <div><FontAwesomeIcon icon={faRocket} size="6x" className="cardicn text-center"/></div>
              <Card.Text>Login to use Coact to manage your S3DF resources</Card.Text>
              <Button variant="secondary" size="lg" href="/login">Login...</Button>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
